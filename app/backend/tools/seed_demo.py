import asyncio
import hashlib
import re
import shutil
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml
from sqlalchemy import delete, func, select, update

from app import clock, media, store
from app.coaching import briefer
from app.config import settings
from app.db import async_session
from app.engine import calendar, metrics, search
from app.engine.run import rebuild
from app.enrichment import vocabulary
from app.models import (
    AgentRun,
    Asset,
    AssetClaim,
    AssetEvidence,
    AssetFile,
    AssetVersion,
    BriefingRun,
    EngineRun,
    EnrichedFact,
    EnrichmentRun,
    EntityCanonical,
    FactCurrent,
    MergeCandidate,
    MetricSnapshot,
    RawEvent,
    SkillRun,
    SkillRunToolCall,
    SlotSkip,
    StudioThread,
    StudioTurn,
    SyncRun,
)
from app.skills import catalog

NOW = clock.now()
MODEL = "claude-sonnet-5"
PROMPT = "2026-08-02.1"
PINS = [
    (SyncRun.started_at, NOW - timedelta(days=1), None),
    (EngineRun.created_at, NOW - timedelta(hours=2), None),
    (FactCurrent.observed_at, NOW - timedelta(hours=1), timedelta(days=1)),
    (RawEvent.ingested_at, NOW - timedelta(hours=1), None),
]
STUDIO_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "studio"
SEED = Path(__file__).resolve().parents[1] / "fixtures" / "seed.yaml"
PLACEHOLDER = re.compile(r"\{([^{}]+)\}")
SPEAKER = re.compile(r"^([^:\n]+):", re.MULTILINE)
AFFILIATION = re.compile(r"\([^()]+\)$")
STUDIO_TABLES = (
    StudioTurn,
    StudioThread,
    SkillRunToolCall,
    SkillRun,
    AgentRun,
    SlotSkip,
    AssetClaim,
    AssetEvidence,
    AssetFile,
    AssetVersion,
    Asset,
)
SKIPPED_SLOT = "linkedin_post"


def topic(calls: list[dict], meeting_name: str) -> dict | None:
    return next((call for call in calls if call["key"] in meeting_name), None)


def company(meeting_name: str) -> str:
    return re.split(r" <> | — ", meeting_name)[0]


def read_seed() -> dict:
    return yaml.safe_load(SEED.read_text())


def filled(text: str, named: dict[str, str]) -> str:
    return PLACEHOLDER.sub(lambda found: named[found[1]], text)


def read_library() -> dict:
    return yaml.safe_load((STUDIO_FIXTURES / "manifest.yaml").read_text())


def version_folder(entry: dict, number: int) -> Path:
    return STUDIO_FIXTURES / entry["dir"] / str(number)


def read_manifest(read: dict, companies: dict) -> dict:
    return {
        "metrics": read["metrics"],
        "goals": {
            name: {key: value for key, value in goal.items() if value is not None}
            for name, goal in read["goals"].items()
        },
        "findings": [
            {"rule": finding["rule"], "entity": companies[finding["call"]]}
            for finding in read["findings"]
        ],
    }


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def our_side(text: str) -> str | None:
    marks = (AFFILIATION.search(label.strip()) for label in SPEAKER.findall(text))
    return next((mark[0] for mark in marks if mark), None)


def sentence(text: str, keyword: str) -> str:
    ours = our_side(text)
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text)]
    parts = [p for p in parts if len(p) > 30]
    prospect = [p for p in parts if ours is None or ours not in p.split(":")[0]]
    for p in prospect:
        if keyword.replace("_", " ") in p.lower():
            return re.sub(r"^[^:]+:\s*", "", p)
    pool = prospect or parts
    return re.sub(r"^[^:]+:\s*", "", pool[len(keyword) % len(pool)])


async def facts_of(s, entity_type: str, attr: str) -> list[tuple]:
    return (
        await s.execute(
            select(FactCurrent.canonical_id, FactCurrent.value)
            .join(
                EntityCanonical,
                EntityCanonical.canonical_id == FactCurrent.canonical_id,
            )
            .where(FactCurrent.attr == attr, EntityCanonical.entity_type == entity_type)
            .order_by(EntityCanonical.minted_seq)
        )
    ).all()


def fact(cid, entity_type, reading, attr, value, quote, text, vocab, when):
    return EnrichedFact(
        canonical_id=cid,
        entity_type=entity_type,
        reading=reading,
        attr=attr,
        value=value,
        quote=quote,
        quote_verified=quote in text,
        input_sha=sha(text),
        vocabulary_sha=vocab,
        model=MODEL,
        prompt_version=PROMPT,
        created_at=when,
    )


def run(reading: str, vocab: str, read: int, when: datetime) -> EnrichmentRun:
    return EnrichmentRun(
        reading=reading,
        vocabulary_sha=vocab,
        model=MODEL,
        prompt_version=PROMPT,
        read=read,
        failed=0,
        truncated_at_cap=False,
        created_at=when,
    )


def briefing(
    role: str, text: str, when: datetime, duration_ms: int, manifest: dict
) -> BriefingRun:
    return BriefingRun(
        role=role,
        ok=True,
        model=MODEL,
        prompt_version=PROMPT,
        prompts_sha=briefer.prompts_sha(),
        input_sha=sha(text),
        read_manifest=manifest,
        briefing=text,
        error=None,
        duration_ms=duration_ms,
        created_at=when,
    )


async def seed_meetings(s, vocab: str) -> int:
    calls = read_seed()["calls"]
    rows = await facts_of(s, "meeting", "transcript")
    names = dict(await facts_of(s, "meeting", "name"))
    n = 0
    for i, (cid, text) in enumerate(rows):
        call = topic(calls, names.get(cid, ""))
        if call is None:
            continue
        when = NOW - timedelta(hours=2, minutes=7 * i)
        labels = [("interest", call["interest"]), ("timing", call["timing"])]
        labels += [("pain_points", p) for p in call["pain_points"]]
        for attr, value in labels:
            quote = sentence(text, value if attr == "pain_points" else attr)
            if not call["verified"] and attr == "interest":
                quote = "we are basically ready to sign whenever you are"
            s.add(
                fact(
                    cid, "meeting", "sales_call", attr, value, quote, text, vocab, when
                )
            )
            n += 1
    s.add(run("sales_call", vocab, len(rows), NOW - timedelta(hours=2)))
    return n


async def seed_tickets(s, vocab: str) -> int:
    tickets = read_seed()["tickets"]
    n = 0
    for k, (cid, subject) in enumerate(await facts_of(s, "ticket", "subject")):
        label = next(
            (t["complaint"] for t in tickets if subject.startswith(t["subject"])), None
        )
        if label is None:
            continue
        quote = subject if k % 7 else "customer says the whole account is locked"
        when = NOW - timedelta(hours=1, minutes=3 * k)
        s.add(
            fact(
                cid,
                "ticket",
                "support_ticket",
                "complaint",
                label,
                quote,
                subject,
                vocab,
                when,
            )
        )
        n += 1
    s.add(run("support_ticket", vocab, n, NOW - timedelta(hours=1)))
    return n


async def companies(s, calls: list[dict]) -> dict[str, str]:
    named = {}
    for _cid, name in await facts_of(s, "meeting", "name"):
        call = topic(calls, name)
        if call is not None:
            named[call["key"]] = company(name)
    return named


async def seed_briefings(s) -> int:
    seed = read_seed()
    named = await companies(s, seed["calls"])
    manifest = read_manifest(seed["read"], named)
    n = 0
    for j, (role, texts) in enumerate(seed["briefings"].items()):
        for d, earlier in enumerate(texts["history"]):
            when = NOW - timedelta(days=5 - d, hours=1, minutes=20 * j)
            text = filled(earlier, named)
            s.add(briefing(role, text, when, 2900 + 300 * d, manifest))
            n += 1
        await s.flush()
        latest = NOW - timedelta(hours=1, minutes=20 * j)
        text = filled(texts["latest"], named)
        s.add(briefing(role, text, latest, 3400 + 900 * j, manifest))
        n += 1
    return n


async def seed_snapshots(s) -> int:
    n = 0
    pinned: list[datetime] = []
    for days in (3, 2, 1):
        n += await metrics.record_snapshots(s)
        when = NOW - timedelta(days=days)
        await s.execute(
            update(MetricSnapshot)
            .where(MetricSnapshot.recorded_at.not_in(pinned))
            .values(recorded_at=when)
        )
        pinned.append(when)
    return n


async def pin(s, column, target: datetime, window: timedelta | None) -> int:
    newest = await s.scalar(select(func.max(column)))
    if newest is None:
        return 0
    shift = update(column.class_).values({column.key: column + (target - newest)})
    if window is not None:
        shift = shift.where(column >= newest - window)
    return (await s.execute(shift)).rowcount


async def pin_engine_run_durations(s) -> int:
    ids = (
        (await s.execute(select(EngineRun.id).order_by(EngineRun.seq.desc())))
        .scalars()
        .all()
    )
    for index, run_id in enumerate(ids):
        await s.execute(
            update(EngineRun)
            .where(EngineRun.id == run_id)
            .values(duration_ms=max(100, 1587 - 300 * index))
        )
    return len(ids)


async def seed_candidates(s) -> int:
    lookalikes = read_seed()["lookalikes"]
    for pair in lookalikes:
        for record in pair["records"]:
            await store.save_raw(
                s,
                source=record["source"],
                object_type=record["object_type"],
                source_id=record["source_id"],
                raw_payload={"id": record["source_id"], **record["fields"]},
            )
    await s.commit()
    await rebuild(s)
    for pair in lookalikes:
        if pair["decided"] is None:
            continue
        left, right = sorted(
            f"{record['source']}|person|{record['source_id']}"
            for record in pair["records"]
        )
        await s.execute(
            update(MergeCandidate)
            .where(
                MergeCandidate.left_anchor == left,
                MergeCandidate.right_anchor == right,
            )
            .values(status=pair["decided"], decided_at=NOW - timedelta(hours=3))
        )
    await s.commit()
    await rebuild(s)
    return await s.scalar(select(func.count()).select_from(MergeCandidate))


@dataclass(frozen=True)
class Rebase:
    made_at: datetime

    def at(self, stamp: str) -> datetime:
        return datetime.fromisoformat(stamp) + (NOW - self.made_at)

    def on(self, stamp: str) -> date:
        return self.at(f"{stamp}T{self.made_at.timetz().isoformat()}").date()


def asset_row(entry: dict, rebase: Rebase) -> Asset:
    slot_date = entry.get("slot_date")
    return Asset(
        name=entry["name"],
        kind=entry["kind"],
        skill=entry["skill"],
        look=entry.get("look"),
        ratio=entry.get("ratio"),
        origin=entry["origin"],
        slot_date=None if slot_date is None else rebase.on(slot_date),
        slot_name=entry.get("slot_name"),
        created_at=rebase.at(entry["created_at"]),
    )


def run_row(entry: dict, version: dict, seq: int, finished: datetime) -> SkillRun:
    return SkillRun(
        skill=entry["skill"],
        skill_sha=catalog.load(entry["skill"]).sha,
        caller=entry["origin"],
        asset_seq=seq,
        version=version["version"],
        status=entry["status"],
        model=version["model"],
        tokens_in=version["tokens_in"],
        tokens_out=version["tokens_out"],
        duration_ms=version["duration_ms"],
        started_at=finished - timedelta(milliseconds=version["duration_ms"]),
        finished_at=finished,
    )


async def seed_version(
    s, entry: dict, seq: int, version: dict, rebase: Rebase, counts: Counter
) -> SkillRun:
    number, when = version["version"], rebase.at(version["created_at"])
    folder = version_folder(entry, number)
    s.add(
        AssetVersion(
            asset_seq=seq, version=number, note=version["note"], created_at=when
        )
    )
    for file in version["files"]:
        data = (folder / file["path"]).read_bytes()
        written = media.write(seq, number, file["path"], data)
        s.add(AssetFile(asset_seq=seq, version=number, created_at=when, **written))
    s.add_all(
        AssetClaim(asset_seq=seq, version=number, **claim)
        for claim in version["claims"]
    )
    s.add_all(
        AssetEvidence(asset_seq=seq, version=number, **item)
        for item in version["evidence"]
    )
    run = run_row(entry, version, seq, when)
    s.add(run)
    await s.flush()
    s.add_all(
        SkillRunToolCall(skill_run_seq=run.seq, **call)
        for call in version["tool_calls"]
    )
    counts.update(
        asset_version=1,
        asset_file=len(version["files"]),
        asset_claim=len(version["claims"]),
        asset_evidence=len(version["evidence"]),
        skill_run=1,
        skill_run_tool_call=len(version["tool_calls"]),
    )
    return run


def skipped_day() -> date:
    spec = calendar.slots()[SKIPPED_SLOT]
    day = NOW.date()
    return calendar.dates(spec, day + timedelta(days=1), day + timedelta(days=14))[0]


async def seed_studio(s) -> dict:
    for table in STUDIO_TABLES:
        await s.execute(delete(table))
    await s.flush()
    shutil.rmtree(Path(settings.MEDIA_DIR) / "assets", ignore_errors=True)
    library = read_library()
    rebase = Rebase(datetime.fromisoformat(library["made_at"]))
    counts: Counter = Counter()
    opened: dict[int, int] = {}
    for entry in library["assets"]:
        asset = asset_row(entry, rebase)
        s.add(asset)
        await s.flush()
        counts.update(asset=1)
        for version in entry["versions"]:
            run = await seed_version(s, entry, asset.seq, version, rebase, counts)
            opened.setdefault(entry["seq"], run.seq)
    s.add(
        AgentRun(
            agent="marketer",
            trigger="daily",
            read_detail="6 slots, 2 empty",
            made=2,
            duration_ms=84000,
            ok=True,
            error=None,
            created_at=(NOW - timedelta(days=1)).replace(
                hour=6, minute=0, second=0, microsecond=0
            ),
        )
    )
    s.add(
        SlotSkip(
            slot_date=skipped_day(),
            slot_name=SKIPPED_SLOT,
            created_at=NOW - timedelta(days=1),
        )
    )
    thread = library["thread"]
    row = StudioThread(
        title=thread["title"], created_at=rebase.at(thread["created_at"])
    )
    s.add(row)
    await s.flush()
    for turn in thread["turns"]:
        made = turn.get("asset")
        s.add(
            StudioTurn(
                thread_seq=row.seq,
                role=turn["role"],
                text=turn["text"],
                skill_run_seq=None if made is None else opened[made],
                created_at=rebase.at(turn["created_at"]),
            )
        )
    counts.update(
        agent_run=1, slot_skip=1, studio_thread=1, studio_turn=len(thread["turns"])
    )
    return dict(counts)


async def main() -> None:
    readings = vocabulary.load()
    async with async_session() as s:
        candidates = await seed_candidates(s)
        for table in (EnrichedFact, EnrichmentRun, BriefingRun, MetricSnapshot):
            await s.execute(delete(table))
        meetings = await seed_meetings(s, readings["sales_call"].sha)
        tickets = await seed_tickets(s, readings["support_ticket"].sha)
        briefings = await seed_briefings(s)
        studio = await seed_studio(s)
        indexed = await search.index(s)
        pinned = {
            column.class_.__tablename__: await pin(s, column, target, window)
            for column, target, window in PINS
        }
        engine_run_durations = await pin_engine_run_durations(s)
        snapshots = await seed_snapshots(s)
        await s.commit()
    counts = {
        "merge_candidate": candidates,
        "enriched_fact": meetings + tickets,
        "enrichment_run": 2,
        "briefing_run": briefings,
        "search_document": indexed["documents"],
        "search_chunk": indexed["chunks"],
        "metric_snapshot": snapshots,
        **pinned,
        "engine_run_duration_ms": engine_run_durations,
        **studio,
    }
    print(" ".join(f"{k}={v}" for k, v in counts.items()), f"anchor={NOW.isoformat()}")


if __name__ == "__main__":
    asyncio.run(main())
