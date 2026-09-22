import json
import time
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select

from app import clock, llm, media, prompts
from app.config import settings
from app.db import async_session
from app.models import (
    Asset,
    AssetClaim,
    AssetEvidence,
    AssetFile,
    AssetVersion,
    SkillRun,
)
from app.render.client import Painter, Render
from app.skills import catalog, toolbelt
from app.skills.catalog import SkillError

CALLERS = ("chat", "marketer", "mcp")
NAME_CHARS = 256
RESULT_CHARS = 16_000
VERIFIED_SOURCES = ("proof", "transcript")
CLAIMS_FILE, HELD_FILE = "claims.md", "held.md"
NO_SOURCE, HELD_SOURCE = "none", "held"

SAFETY = prompts.text("studio_skill", "safety")
TOOLBELT_NOTE = prompts.text("studio_skill", "toolbelt")
CALLER_NOTES = {
    caller: prompts.text("studio_skill", f"caller_{caller}") for caller in CALLERS
}


@dataclass(frozen=True)
class Ask:
    skill: str
    caller: str
    input: str
    look: str | None = None
    ratio: str | None = None
    slot_date: date | None = None
    slot_name: str | None = None
    asset_seq: int | None = None


@dataclass(frozen=True)
class Started:
    skill_run: int
    asset_seq: int
    version: int


def _name(text: str) -> str:
    first = next(line.strip() for line in text.splitlines() if line.strip())
    return first[:NAME_CHARS]


async def open_run(session, ask: Ask) -> Started:
    if not settings.STUDIO_ENABLED:
        raise SkillError(
            "STUDIO_ENABLED is off. Studio calls a model and a painter, "
            "and it is opt-in on purpose."
        )
    if ask.caller not in CALLERS:
        raise SkillError(f"caller {ask.caller!r} is not one of {', '.join(CALLERS)}")
    skill = catalog.load(ask.skill)
    if not (ask.input or "").strip():
        raise SkillError("the ask is empty: a run starts from words")
    now = clock.now()
    if ask.asset_seq is None:
        asset = Asset(
            name=_name(ask.input),
            kind=skill.makes,
            skill=skill.name,
            look=ask.look,
            ratio=ask.ratio,
            origin=ask.caller,
            slot_date=ask.slot_date,
            slot_name=ask.slot_name,
            created_at=now,
        )
        session.add(asset)
        await session.flush()
        version = 1
    else:
        asset = await session.get(Asset, ask.asset_seq)
        if asset is None:
            raise SkillError(f"no asset {ask.asset_seq} to revise")
        latest = select(func.max(AssetVersion.version)).where(
            AssetVersion.asset_seq == asset.seq
        )
        version = (await session.execute(latest)).scalar() + 1
        if ask.ratio:
            asset.ratio = ask.ratio
    session.add(
        AssetVersion(
            asset_seq=asset.seq, version=version, note=ask.input, created_at=now
        )
    )
    run = SkillRun(
        skill=skill.name,
        skill_sha=skill.sha,
        caller=ask.caller,
        asset_seq=asset.seq,
        version=version,
        status="running",
        started_at=now,
    )
    session.add(run)
    await session.commit()
    return Started(run.seq, asset.seq, version)


def caller_note(caller: str) -> str:
    return f"{CALLER_NOTES[caller]} Today is {clock.now().date().isoformat()}."


def build_system(skill: catalog.Skill, caller: str) -> str:
    lessons = "\n".join(f"- {lesson}" for lesson in skill.lessons) or "- none yet"
    return "\n\n".join(
        (
            SAFETY,
            skill.body,
            f"## Lessons in force\n\n{lessons}",
            TOOLBELT_NOTE,
            caller_note(caller),
        )
    )


def opening(ask: Ask) -> str:
    lines = [f"Caller: {ask.caller}"]
    if ask.look:
        lines.append(f"Look: {ask.look}")
    if ask.ratio:
        lines.append(f"Ratio: {ask.ratio}")
    slot = " ".join(str(part) for part in (ask.slot_name, ask.slot_date) if part)
    if slot:
        lines.append(f"Slot: {slot}")
    if ask.asset_seq is not None:
        lines.append(
            f"Revising asset {ask.asset_seq}: read it with "
            f"assets.read({ask.asset_seq}) before changing what the ask names"
        )
    lines.append(f"Asked for: {ask.input}")
    return "\n".join(lines)


def render_tool_result(name: str, payload) -> str:
    body = json.dumps(payload, indent=1, default=str)
    body = body.replace(toolbelt.FENCE_CLOSE, toolbelt.FENCE_CLOSE.replace("</", "<​/"))
    if len(body) > RESULT_CHARS:
        body = (
            body[:RESULT_CHARS] + f"\n\n[truncated: {name} returned {len(body)} "
            f"characters, capped at {RESULT_CHARS}. Read a narrower thing rather "
            "than treating this as the whole.]"
        )
    return f"{toolbelt.FENCE_OPEN}\n{body}\n{toolbelt.FENCE_CLOSE}"


async def _loop(session, run, bench, system, messages, model_client, outcome):
    tokens = outcome["tokens"]
    for turn in range(1, settings.STUDIO_MAX_TURNS + 1):
        outcome["turns"] = turn
        try:
            response = await llm.converse(
                model=settings.STUDIO_MODEL,
                max_tokens=settings.STUDIO_MAX_TOKENS,
                system=system,
                messages=messages,
                tools=toolbelt.schemas(),
                client_override=model_client,
            )
        except llm.LLMError as exc:
            raise SkillError(str(exc)) from exc
        tokens["in"] += response.usage.input_tokens
        tokens["out"] += response.usage.output_tokens
        run.model, run.tokens_in, run.tokens_out = (
            response.model,
            tokens["in"],
            tokens["out"],
        )
        if response.stop_reason == "refusal":
            raise SkillError("the model declined to run the skill")
        if response.stop_reason == "max_tokens":
            raise SkillError(
                "the answer was cut at STUDIO_MAX_TOKENS before the skill finished"
            )
        calls = [block for block in response.content if block.type == "tool_use"]
        if not calls:
            outcome["answer"] = "".join(
                block.text for block in response.content if block.type == "text"
            )
            return
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for call in calls:
            payload = await toolbelt.call(bench, call.name, call.input)
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": render_tool_result(call.name, payload),
                }
            )
        messages.append({"role": "user", "content": results})
        run.stage = bench.stage
        await session.commit()
    raise SkillError(f"did not finish within {settings.STUDIO_MAX_TURNS} turns")


def _written(bench, path: str) -> str | None:
    if any(item["path"] == path for item in bench.written):
        data = media.read(bench.asset_seq, bench.version, path)
        return data.decode(errors="replace")
    return None


def _lines(text: str) -> list[str]:
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("- "):
            line = line[2:].strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return lines


def parse_claims(text: str) -> list[dict]:
    claims = []
    for line in _lines(text):
        parts = [part.strip() for part in line.rsplit("|", 2)]
        claim, source, ref = (parts + ["", ""])[:3]
        claims.append(
            {
                "text": claim,
                "source": source or NO_SOURCE,
                "ref": ref or None,
                "verified": source in VERIFIED_SOURCES and bool(ref),
            }
        )
    return claims


async def execute(
    session,
    seq: int,
    ask: Ask,
    *,
    model_client=None,
    paint_client=None,
    render_client=None,
) -> dict:
    run = await session.get(SkillRun, seq)
    if run is None:
        raise SkillError(f"no skill run {seq}")
    started = time.monotonic()
    bench = toolbelt.Bench(
        session,
        run.seq,
        run.asset_seq,
        run.version,
        painter=Painter(paint_client),
        renderer=Render(render_client),
    )
    outcome = {"answer": "", "turns": 0, "error": None, "tokens": {"in": 0, "out": 0}}
    try:
        skill = catalog.load(ask.skill)
        messages = [{"role": "user", "content": opening(ask)}]
        system = build_system(skill, ask.caller)
        await _loop(session, run, bench, system, messages, model_client, outcome)
    except SkillError as exc:
        outcome["error"] = str(exc)
    except Exception as exc:
        outcome["error"] = f"{type(exc).__name__}: {exc}"

    claims = parse_claims(_written(bench, CLAIMS_FILE) or "")
    held = _written(bench, HELD_FILE)
    now = clock.now()
    where = {"asset_seq": bench.asset_seq, "version": bench.version}
    for item in bench.written:
        session.add(AssetFile(**where, **item, created_at=now))
    for claim in claims:
        session.add(
            AssetClaim(
                **where,
                text=claim["text"],
                source_kind=claim["source"],
                source_ref=claim["ref"],
                verified=claim["verified"],
            )
        )
    for line in _lines(held or ""):
        session.add(
            AssetClaim(
                **where,
                text=line,
                source_kind=HELD_SOURCE,
                source_ref=None,
                verified=False,
            )
        )
    for item in bench.read:
        session.add(AssetEvidence(**where, **item))
    if outcome["error"]:
        status = "failed"
    elif held is not None or any(not claim["verified"] for claim in claims):
        status = "held"
    else:
        status = "ok"
    run.status, run.error = status, outcome["error"]
    run.duration_ms = int((time.monotonic() - started) * 1000)
    run.finished_at = now
    await session.commit()
    return {
        "skill_run": run.seq,
        "status": status,
        "error": outcome["error"],
        "answer": outcome["answer"],
        "turns": outcome["turns"],
        "files": list(bench.written),
        "claims": claims,
        "tokens": outcome["tokens"],
    }


async def execute_detached(seq: int, ask: Ask) -> None:
    async with async_session() as session:
        await execute(session, seq, ask)
