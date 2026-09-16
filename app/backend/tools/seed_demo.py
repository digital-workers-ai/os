import asyncio
import hashlib
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path

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
PLAN = {
    "Globex": ("strong", "this_quarter", ["manual_work", "reporting_gaps"], True),
    "Stark": ("weak", "no_timeline", ["support_quality", "pricing"], False),
    "Wayne": ("strong", "immediate", ["pricing", "onboarding_time"], True),
    "Initech": ("moderate", "next_quarter", ["missing_features"], True),
    "Pied Piper": (
        "moderate",
        "next_quarter",
        ["security_compliance", "integration_complexity"],
        True,
    ),
    "Cyberdyne": ("none", "next_year", ["vendor_lock_in"], False),
}
TICKETS = {
    "API rate limit": "access",
    "Billing discrepancy": "billing",
    "Cannot export": "bug",
    "Feature request": "feature_request",
    "Feature suggestion": "feature_request",
    "Getting started": "how_to",
    "How to set up SSO": "access",
    "Integration failing": "bug",
    "Need invoice": "billing",
    "Payment method": "billing",
}
HISTORY = {
    "ceo": [
        "Revenue is at $16,540 MRR against the $20,000 quarter goal, with 9 open "
        "deals. The pipeline rule found one deal with no next step. Sales calls "
        "are not being read yet, so interest is not measured.",
        "Revenue is at $16,700 MRR and 10 open deals worth $341,000. No goal is "
        "met. One high-severity finding is open: Initech has had no activity in "
        "fourteen days.",
        "Revenue is at $16,820 MRR, short of the $20,000 quarter goal, with 11 "
        "open deals in pipeline. No sales calls have been read yet, so buying "
        "interest could not be measured this week.",
        "Revenue moved to $16,950 MRR with 12 open deals. The first four sales "
        "calls were read: one strong, two moderate, one weak. Two high-severity "
        "findings are open, both deals with no next step.",
        "Revenue is at $17,020 MRR and 13 open deals worth $388,000. Wayne "
        "Enterprises reads as strong interest and wants to move immediately. "
        "Stark Industries has escalated a billing dispute and says it will buy "
        "nothing more until it is resolved.",
    ],
    "head_of_sales": [
        "Nine open deals. Initech has had no activity in two weeks and no next "
        "step is recorded. Calls are not being read yet, so there is no interest "
        "signal.",
        "Ten open deals worth $341,000. Initech is still idle. Globex booked a "
        "call for next week about expanding to the growth team.",
        "Eleven open deals, none with a recorded next step older than a week. "
        "Sales calls have not been read yet, so there is no interest signal to "
        "act on.",
        "Four calls read. Globex is strong for this quarter and wants reporting "
        "sales already has. Initech is moderate and pushed to next quarter. Two "
        "deals have no next step recorded.",
        "Wayne Enterprises came in strong and immediate, gated on pricing. Pied "
        "Piper is blocked on a security review. Three deals have no next step, "
        "all three older than ten days.",
    ],
}
BRIEFS = {
    "ceo": (
        "Revenue is holding at 17,147 MRR with 14 open deals worth 412,000 in "
        "pipeline. Two of the six sales calls this week show strong buying "
        "interest, Globex and Wayne Enterprises, and both name pricing or "
        "reporting as the thing standing between them and a signature.\n\n"
        "The one to watch is Stark Industries: the billing escalation call reads "
        "as weak interest with support quality named twice. If that renewal "
        "slips, the quarter target of 20,000 MRR moves out of reach."
    ),
    "head_of_sales": (
        "Wayne Enterprises wants to move immediately and is gated on pricing and "
        "onboarding time; that is the deal to close first. Globex is strong for "
        "this quarter and asked for reporting they cannot get today.\n\n"
        "Initech and Pied Piper are both moderate and next quarter; Pied Piper "
        "is blocked on a security review, so get the compliance pack in front of "
        "them now. Cyberdyne is a no for this year. Three findings are open "
        "against your pipeline hygiene rules, all of them deals with no next "
        "step."
    ),
}
MANIFEST = {
    "metrics": {
        "mrr": 17147.0,
        "open_deals": 14,
        "pipeline_value": 412000.0,
        "sales_calls_strong_interest": 2,
    },
    "goals": {
        "mrr_target": {"target": 20000, "current": 17147.0, "met": False},
        "deals_with_next_step": {"met": False},
    },
    "findings": [
        {"rule": "deal_without_next_step", "entity": "Stark Industries"},
        {"rule": "deal_without_next_step", "entity": "Cyberdyne"},
        {"rule": "stale_deal", "entity": "Initech"},
    ],
}
LOOKALIKES = {
    "carlos": (
        ("zendesk", "users", "29001", {"name": "Carlos Ch", "phone": "+14155550101"}),
        (
            "intercom",
            "contacts",
            "con_demo_carlos",
            {"name": "C Chinchilla", "phone": "+1 415 555 0101"},
        ),
    ),
    "maria": (
        (
            "zendesk",
            "users",
            "29002",
            {"name": "Maria Lopez", "email": "maria@zenith-labs.io"},
        ),
        (
            "intercom",
            "contacts",
            "con_demo_maria",
            {"name": "M. Lopez", "email": "m.lopez@zenith-labs.io"},
        ),
    ),
    "alex": (
        (
            "zendesk",
            "users",
            "29003",
            {"name": "Alex Rivera", "email": "alex@northwind.co"},
        ),
        (
            "intercom",
            "contacts",
            "con_demo_alex",
            {"name": "Alexandra Rivera", "email": "alexandra@northwind.co"},
        ),
    ),
}
DECIDED = {"maria": "confirmed", "alex": "rejected"}
STUDIO_MODEL = "claude-opus-5"
STUDIO_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "studio"
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
CLAIMS = "claims.md"
BUILD = "build.md"
HELD_CLAIM = "Teams close their quarter twice as fast with DW-OS."
EVIDENCE = (
    ("proof.md", "The gate holds 100% line and branch coverage; never red."),
    ("voice.md", "Plain, specific, concrete. No hype, no hashtags, no emoji."),
)
IMAGE_TOOLS = ("image_paint", "image_render")
TEXT_TOOLS = ("brand_read", "files_write")
TOOL_DETAIL = {
    "image_paint": "painted one picture, no words in it",
    "image_render": "rendered the card over the picture",
    "brand_read": "read voice.md, language.md and proof.md",
    "files_write": "wrote every file the ask named",
}
CARD_FILES = (
    ("content.yaml", "content.yaml"),
    ("image.png", "stat-card.png"),
    (CLAIMS, CLAIMS),
    (BUILD, BUILD),
)
QUOTE_FILES = (("image.png", "quote-card.png"), (CLAIMS, CLAIMS), (BUILD, BUILD))
POST_FILES = (
    ("post.md", "post.md"),
    ("image.png", "stat-card.png"),
    (CLAIMS, CLAIMS),
    (BUILD, BUILD),
)
LETTER_FILES = (
    ("newsletter.md", "newsletter.md"),
    ("newsletter.html", "newsletter.html"),
    (CLAIMS, CLAIMS),
    (BUILD, BUILD),
)
BLOG_FILES = (("post.md", "blog.md"), (CLAIMS, CLAIMS), (BUILD, BUILD))
CAROUSEL_FILES = (
    ("slide-01.png", "carousel-01.png"),
    ("slide-02.png", "carousel-02.png"),
    ("slide-03.png", "carousel-03.png"),
    (CLAIMS, CLAIMS),
    (BUILD, BUILD),
)
STUDIO_ASSETS = (
    {
        "name": "100% line and branch coverage",
        "kind": "image",
        "skill": "dw-image",
        "look": "stat-card",
        "ratio": "1:1",
        "origin": "chat",
        "days": 0,
        "hours": 2,
        "tools": IMAGE_TOOLS,
        "versions": (
            ("A stat card on the test gate, stat-card at 1:1", CARD_FILES),
            ("shorter label", CARD_FILES),
        ),
    },
    {
        "name": "Every number can tell you which tool it came from",
        "kind": "image",
        "skill": "dw-image",
        "look": "quote-card",
        "ratio": "1:1",
        "origin": "chat",
        "days": 0,
        "hours": 3,
        "tools": IMAGE_TOOLS,
        "status": "held",
        "versions": (("A quote card from the line on tracing a number", QUOTE_FILES),),
    },
    {
        "name": "Why a rebuild never touches the raw store",
        "kind": "blog",
        "skill": "dw-blog",
        "origin": "chat",
        "days": 1,
        "hours": 2,
        "tools": TEXT_TOOLS,
        "versions": (("Explain the rebuild to the engineer", BLOG_FILES),),
    },
    {
        "name": "Where a number comes from",
        "kind": "carousel",
        "skill": "dw-carousel",
        "look": "carousel",
        "ratio": "4:5",
        "origin": "mcp",
        "days": 1,
        "hours": 3,
        "tools": IMAGE_TOOLS,
        "versions": (("Three facts about DW-OS, carousel at 4:5", CAROUSEL_FILES),),
    },
    {
        "name": "A spreadsheet has no test gate",
        "kind": "post",
        "skill": "dw-post",
        "look": "stat-card",
        "ratio": "1:1",
        "origin": "marketer",
        "slot": ("linkedin_post", 2),
        "days": 2,
        "hours": 2,
        "tools": IMAGE_TOOLS,
        "versions": (("One thing a spreadsheet cannot do, for the owner", POST_FILES),),
    },
    {
        "name": "The review queue this week",
        "kind": "newsletter",
        "skill": "dw-newsletter",
        "origin": "marketer",
        "slot": ("newsletter_weekly", 4),
        "days": 2,
        "hours": 3,
        "tools": TEXT_TOOLS,
        "versions": (("This week's letter to the operator", LETTER_FILES),),
    },
)
SKIPPED_SLOT = "linkedin_post"
THREAD_TITLE = "a post on the coverage gate"
THREAD_TURNS = (
    ("person", "Make a post about the coverage gate for the owner, with the image."),
    ("studio", "Writing one post on the test gate, with a stat card at 1:1."),
)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def sentence(text: str, keyword: str) -> str:
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text)]
    parts = [p for p in parts if len(p) > 30]
    prospect = [p for p in parts if "(OS)" not in p.split(":")[0]]
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


def briefing(role: str, text: str, when: datetime, duration_ms: int) -> BriefingRun:
    return BriefingRun(
        role=role,
        ok=True,
        model=MODEL,
        prompt_version=PROMPT,
        prompts_sha=briefer.prompts_sha(),
        input_sha=sha(text),
        read_manifest=MANIFEST,
        briefing=text,
        error=None,
        duration_ms=duration_ms,
        created_at=when,
    )


async def seed_meetings(s, vocab: str) -> int:
    rows = await facts_of(s, "meeting", "transcript")
    names = dict(await facts_of(s, "meeting", "name"))
    n = 0
    for i, (cid, text) in enumerate(rows):
        key = next((k for k in PLAN if k in names.get(cid, "")), None)
        if key is None:
            continue
        interest, timing, pains, verified = PLAN[key]
        when = NOW - timedelta(hours=2, minutes=7 * i)
        labels = [("interest", interest), ("timing", timing)]
        labels += [("pain_points", p) for p in pains]
        for attr, value in labels:
            quote = sentence(text, value if attr == "pain_points" else attr)
            if not verified and attr == "interest":
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
    n = 0
    for k, (cid, subject) in enumerate(await facts_of(s, "ticket", "subject")):
        label = next((v for key, v in TICKETS.items() if subject.startswith(key)), None)
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


async def seed_briefings(s) -> int:
    n = 0
    for j, (role, text) in enumerate(BRIEFS.items()):
        for d, earlier in enumerate(HISTORY[role]):
            when = NOW - timedelta(days=5 - d, hours=1, minutes=20 * j)
            s.add(briefing(role, earlier, when, 2900 + 300 * d))
            n += 1
        await s.flush()
        s.add(
            briefing(
                role, text, NOW - timedelta(hours=1, minutes=20 * j), 3400 + 900 * j
            )
        )
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
    for records in LOOKALIKES.values():
        for source, object_type, source_id, fields in records:
            payload = {"id": source_id, **fields}
            await store.save_raw(
                s,
                source=source,
                object_type=object_type,
                source_id=source_id,
                raw_payload=payload,
            )
    await s.commit()
    await rebuild(s)
    for pair, status in DECIDED.items():
        left, right = sorted(
            f"{source}|person|{source_id}"
            for source, _object_type, source_id, _fields in LOOKALIKES[pair]
        )
        await s.execute(
            update(MergeCandidate)
            .where(
                MergeCandidate.left_anchor == left,
                MergeCandidate.right_anchor == right,
            )
            .values(status=status, decided_at=NOW - timedelta(hours=3))
        )
    await s.commit()
    await rebuild(s)
    return await s.scalar(select(func.count()).select_from(MergeCandidate))


def claim_rows(seq, version, held) -> list:
    lines = (STUDIO_FIXTURES / CLAIMS).read_text().strip().splitlines()
    rows = []
    for line in lines:
        text, source_kind, source_ref = (part.strip() for part in line.split("|"))
        rows.append(
            AssetClaim(
                asset_seq=seq,
                version=version,
                text=text,
                source_kind=source_kind,
                source_ref=source_ref,
                verified=True,
            )
        )
    if held:
        rows.append(
            AssetClaim(
                asset_seq=seq,
                version=version,
                text=HELD_CLAIM,
                source_kind="none",
                source_ref=None,
                verified=False,
            )
        )
    return rows


def evidence_rows(seq, version) -> list:
    return [
        AssetEvidence(
            asset_seq=seq, version=version, kind="brand", ref=ref, detail=detail
        )
        for ref, detail in EVIDENCE
    ]


def run_row(spec, number, seq, version, when) -> SkillRun:
    return SkillRun(
        skill=spec["skill"],
        skill_sha=catalog.load(spec["skill"]).sha,
        caller=spec["origin"],
        asset_seq=seq,
        version=version,
        stage=None,
        status=spec.get("status", "ok"),
        error=None,
        model=STUDIO_MODEL,
        tokens_in=8200 + 730 * number,
        tokens_out=1140 + 260 * number,
        duration_ms=38000 + 4200 * number,
        started_at=when - timedelta(minutes=2),
        finished_at=when,
    )


def asset_row(spec, created) -> Asset:
    slot_name, slot_days = spec.get("slot", (None, None))
    slot_date = None if slot_name is None else (NOW - timedelta(days=slot_days)).date()
    return Asset(
        name=spec["name"],
        kind=spec["kind"],
        skill=spec["skill"],
        look=spec.get("look"),
        ratio=spec.get("ratio"),
        origin=spec["origin"],
        slot_date=slot_date,
        slot_name=slot_name,
        feedback=None,
        created_at=created,
    )


def skipped_day() -> datetime.date:
    spec = calendar.slots()[SKIPPED_SLOT]
    day = NOW.date()
    return calendar.dates(spec, day + timedelta(days=1), day + timedelta(days=14))[0]


async def seed_studio(s) -> dict:
    for table in STUDIO_TABLES:
        await s.execute(delete(table))
    await s.flush()
    shutil.rmtree(Path(settings.MEDIA_DIR) / "assets", ignore_errors=True)
    counts = dict.fromkeys(("asset_version", "asset_file", "asset_claim"), 0)
    runs: dict = {}
    for number, spec in enumerate(STUDIO_ASSETS):
        created = NOW - timedelta(days=spec["days"], hours=spec["hours"])
        asset = asset_row(spec, created)
        s.add(asset)
        await s.flush()
        for index, (note, files) in enumerate(spec["versions"]):
            version, when = index + 1, created + timedelta(minutes=30 * index)
            s.add(
                AssetVersion(
                    asset_seq=asset.seq, version=version, note=note, created_at=when
                )
            )
            for path, fixture in files:
                written = media.write(
                    asset.seq, version, path, (STUDIO_FIXTURES / fixture).read_bytes()
                )
                s.add(
                    AssetFile(
                        asset_seq=asset.seq,
                        version=version,
                        path=written["path"],
                        media_type=written["media_type"],
                        bytes=written["bytes"],
                        created_at=when,
                    )
                )
            claims = claim_rows(asset.seq, version, "status" in spec)
            s.add_all(claims + evidence_rows(asset.seq, version))
            run = run_row(spec, number, asset.seq, version, when)
            s.add(run)
            await s.flush()
            for tool in spec["tools"]:
                s.add(
                    SkillRunToolCall(
                        skill_run_seq=run.seq,
                        tool=tool,
                        ok=True,
                        duration_ms=1400 + 90 * number,
                        detail=TOOL_DETAIL[tool],
                    )
                )
            counts["asset_version"] += 1
            counts["asset_file"] += len(files)
            counts["asset_claim"] += len(claims)
            runs[spec["kind"]] = run.seq
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
    opened = NOW - timedelta(days=2, hours=2, minutes=5)
    thread = StudioThread(title=THREAD_TITLE, created_at=opened)
    s.add(thread)
    await s.flush()
    for minutes, (role, text) in enumerate(THREAD_TURNS, 1):
        s.add(
            StudioTurn(
                thread_seq=thread.seq,
                role=role,
                text=text,
                skill_run_seq=runs["post"] if role == "studio" else None,
                created_at=opened + timedelta(minutes=minutes),
            )
        )
    return {
        "asset": len(STUDIO_ASSETS),
        **counts,
        "asset_evidence": counts["asset_version"] * len(EVIDENCE),
        "skill_run": counts["asset_version"],
        "skill_run_tool_call": counts["asset_version"] * 2,
        "agent_run": 1,
        "slot_skip": 1,
        "studio_thread": 1,
        "studio_turn": len(THREAD_TURNS),
    }


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
