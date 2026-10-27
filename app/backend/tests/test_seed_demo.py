import json
import uuid
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import NamedTuple

import pytest
import pytest_asyncio
import yaml
from sqlalchemy import select

from app import llm, media, models
from app.config import settings
from app.engine import calendar as declared
from app.models import (
    AgentRun,
    Asset,
    AssetClaim,
    AssetEvidence,
    AssetFile,
    AssetVersion,
    BriefingRun,
    EnrichedFact,
    EnrichmentRun,
    FactCurrent,
    MergeCandidate,
    RawEvent,
    SkillRun,
    SkillRunToolCall,
    SlotSkip,
    StudioThread,
    StudioTurn,
)
from app.skills import catalog
from tests import ground_truth
from tools import seed_demo

NOW = datetime(2026, 9, 4, 12, tzinfo=UTC)
MANIFEST = seed_demo.STUDIO_FIXTURES / "manifest.yaml"
MODEL = "claude-opus-5"
SEEDED = Path(__file__).with_name("seed_demo_rows.json")
LISTED = {
    "files": "asset_file",
    "claims": "asset_claim",
    "evidence": "asset_evidence",
    "tool_calls": "skill_run_tool_call",
}


def at(month, day, hour, minute=0) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=UTC)


PROOF = (
    (
        "The suite holds 100% line and branch coverage, and nothing is committed "
        "on red.",
        "The gate",
    ),
    (
        "Every number reports which tool it came from, which records it counted, "
        "and which of those records were missing the field.",
        "Introduction",
    ),
    (
        "A rebuild never touches the raw store, the snapshots, what the AI parts "
        "wrote, or the review decisions people made.",
        "How a Rebuild Works",
    ),
)
HELD = ("Teams close their quarter twice as fast with DW-OS.", "none", None, False)
EVIDENCE = (
    ("proof.md", "The gate holds 100% line and branch coverage; never red."),
    ("voice.md", "Plain, specific, concrete. No hype, no hashtags, no emoji."),
)
IMAGE_TOOLS = (
    ("image_paint", "painted one picture, no words in it"),
    ("image_render", "rendered the card over the picture"),
)
TEXT_TOOLS = (
    ("brand_read", "read voice.md, language.md and proof.md"),
    ("files_write", "wrote every file the ask named"),
)
BUILD = ("build.md", "text/markdown", 235)
CLAIMS = ("claims.md", "text/markdown", 391)
STAT_CARD = ("image.png", "image/png", 55672)
CARD = (BUILD, CLAIMS, ("content.yaml", "text/yaml", 121), STAT_CARD)
QUOTE = (BUILD, CLAIMS, ("image.png", "image/png", 73835))
BLOG = (BUILD, CLAIMS, ("post.md", "text/markdown", 1349))
CAROUSEL = (
    BUILD,
    CLAIMS,
    ("slide-01.png", "image/png", 35984),
    ("slide-02.png", "image/png", 68401),
    ("slide-03.png", "image/png", 38788),
)
POST = (BUILD, CLAIMS, STAT_CARD, ("post.md", "text/markdown", 623))
LETTER = (
    BUILD,
    CLAIMS,
    ("newsletter.html", "text/html", 1393),
    ("newsletter.md", "text/markdown", 576),
)
ASSETS = (
    {
        "name": "100% line and branch coverage",
        "kind": "image",
        "skill": "dw-image",
        "look": "stat-card",
        "ratio": "1:1",
        "origin": "chat",
        "slot_date": None,
        "slot_name": None,
        "feedback": None,
        "created_at": at(9, 4, 10),
        "status": "ok",
    },
    {
        "name": "Every number can tell you which tool it came from",
        "kind": "image",
        "skill": "dw-image",
        "look": "quote-card",
        "ratio": "1:1",
        "origin": "chat",
        "slot_date": None,
        "slot_name": None,
        "feedback": None,
        "created_at": at(9, 4, 9),
        "status": "held",
    },
    {
        "name": "Why a rebuild never touches the raw store",
        "kind": "blog",
        "skill": "dw-blog",
        "look": None,
        "ratio": None,
        "origin": "chat",
        "slot_date": None,
        "slot_name": None,
        "feedback": None,
        "created_at": at(9, 3, 10),
        "status": "ok",
    },
    {
        "name": "Where a number comes from",
        "kind": "carousel",
        "skill": "dw-carousel",
        "look": "carousel",
        "ratio": "4:5",
        "origin": "mcp",
        "slot_date": None,
        "slot_name": None,
        "feedback": None,
        "created_at": at(9, 3, 9),
        "status": "ok",
    },
    {
        "name": "A spreadsheet has no test gate",
        "kind": "post",
        "skill": "dw-linkedin-post",
        "look": "stat-card",
        "ratio": "1:1",
        "origin": "marketer",
        "slot_date": date(2026, 9, 2),
        "slot_name": "linkedin_post",
        "feedback": None,
        "created_at": at(9, 2, 10),
        "status": "ok",
    },
    {
        "name": "The review queue this week",
        "kind": "newsletter",
        "skill": "dw-newsletter",
        "look": None,
        "ratio": None,
        "origin": "marketer",
        "slot_date": date(2026, 8, 31),
        "slot_name": "newsletter_weekly",
        "feedback": None,
        "created_at": at(9, 2, 9),
        "status": "ok",
    },
)
ASSET_COLUMNS = tuple(key for key in ASSETS[0] if key != "status")


class Made(NamedTuple):
    asset: int
    version: int
    note: str
    when: datetime
    files: tuple
    tools: tuple
    tokens_in: int
    tokens_out: int
    duration_ms: int
    call_ms: int


VERSIONS = (
    Made(
        1,
        1,
        "A stat card on the test gate, stat-card at 1:1",
        at(9, 4, 10),
        CARD,
        IMAGE_TOOLS,
        8200,
        1140,
        38000,
        1400,
    ),
    Made(
        1,
        2,
        "shorter label",
        at(9, 4, 10, 30),
        CARD,
        IMAGE_TOOLS,
        8200,
        1140,
        38000,
        1400,
    ),
    Made(
        2,
        1,
        "A quote card from the line on tracing a number",
        at(9, 4, 9),
        QUOTE,
        IMAGE_TOOLS,
        8930,
        1400,
        42200,
        1490,
    ),
    Made(
        3,
        1,
        "Explain the rebuild to the engineer",
        at(9, 3, 10),
        BLOG,
        TEXT_TOOLS,
        9660,
        1660,
        46400,
        1580,
    ),
    Made(
        4,
        1,
        "Three facts about DW-OS, carousel at 4:5",
        at(9, 3, 9),
        CAROUSEL,
        IMAGE_TOOLS,
        10390,
        1920,
        50600,
        1670,
    ),
    Made(
        5,
        1,
        "One thing a spreadsheet cannot do, for the owner",
        at(9, 2, 10),
        POST,
        IMAGE_TOOLS,
        11120,
        2180,
        54800,
        1760,
    ),
    Made(
        6,
        1,
        "This week's letter to the operator",
        at(9, 2, 9),
        LETTER,
        TEXT_TOOLS,
        11850,
        2440,
        59000,
        1850,
    ),
)
COUNTS = {
    "asset": 6,
    "asset_version": 7,
    "asset_file": 27,
    "asset_claim": 22,
    "asset_evidence": 14,
    "skill_run": 7,
    "skill_run_tool_call": 14,
    "agent_run": 1,
    "slot_skip": 1,
    "studio_thread": 1,
    "studio_turn": 2,
}
SMALL = {
    "made_at": "2026-09-01T12:00:00+00:00",
    "model": MODEL,
    "assets": [
        {
            "seq": 9,
            "dir": "nine",
            "name": "One number",
            "kind": "post",
            "skill": "dw-linkedin-post",
            "look": "stat-card",
            "ratio": "1:1",
            "origin": "marketer",
            "slot_date": "2026-08-28",
            "slot_name": "linkedin_post",
            "status": "held",
            "created_at": "2026-09-01T09:00:00+00:00",
            "versions": [
                {
                    "version": 1,
                    "note": "One number, for the owner",
                    "created_at": "2026-09-01T09:00:00+00:00",
                    "files": [
                        {"path": "post.md", "media_type": "text/markdown", "bytes": 5}
                    ],
                    "claims": [
                        {
                            "text": "Nobody checked this.",
                            "source_kind": "none",
                            "source_ref": None,
                            "verified": False,
                        }
                    ],
                    "evidence": [
                        {"kind": "brand", "ref": "voice.md", "detail": "Plain."}
                    ],
                    "tool_calls": [
                        {
                            "tool": "files_write",
                            "ok": True,
                            "duration_ms": 10,
                            "detail": "post.md",
                        }
                    ],
                    "model": MODEL,
                    "tokens_in": 10,
                    "tokens_out": 2,
                    "duration_ms": 60000,
                }
            ],
        }
    ],
    "thread": {
        "title": "one number",
        "created_at": "2026-09-01T08:59:00+00:00",
        "turns": [
            {
                "role": "studio",
                "text": "Writing it.",
                "created_at": "2026-09-01T09:00:00+00:00",
                "asset": 9,
            }
        ],
    },
}


@pytest_asyncio.fixture(autouse=True)
def anchored(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "MEDIA_DIR", str(tmp_path / "media"))
    monkeypatch.setattr(seed_demo, "NOW", NOW)


@pytest_asyncio.fixture
async def seeded(session):
    counts = await seed_demo.seed_studio(session)
    await session.flush()
    return counts


async def rows(session, model, *order) -> list:
    return (await session.execute(select(model).order_by(*order))).scalars().all()


def test_manifest_lists_the_sample_library_and_its_files():
    library = yaml.safe_load(MANIFEST.read_text())
    assets = library["assets"]
    assert [asset["name"] for asset in assets] == [spec["name"] for spec in ASSETS]
    versions = [(asset, version) for asset in assets for version in asset["versions"]]
    assert len(versions) == len(VERSIONS)
    for asset, version in versions:
        folder = seed_demo.STUDIO_FIXTURES / asset["dir"] / str(version["version"])
        for file in version["files"]:
            data = (folder / file["path"]).read_bytes()
            assert file["media_type"] == media.media_type(file["path"])
            assert file["bytes"] == len(data)
    for key, table in LISTED.items():
        assert sum(len(version[key]) for _asset, version in versions) == COUNTS[table]
    assert [turn["role"] for turn in library["thread"]["turns"]] == ["person", "studio"]


async def test_counts_report_what_was_written(seeded):
    assert seeded == COUNTS


async def test_assets_are_the_six_the_specs_built(session, seeded):
    found = await rows(session, Asset, Asset.seq)
    assert [{key: getattr(asset, key) for key in ASSET_COLUMNS} for asset in found] == [
        {key: spec[key] for key in ASSET_COLUMNS} for spec in ASSETS
    ]


async def test_versions_carry_their_notes_and_files(session, seeded):
    versions = await rows(
        session, AssetVersion, AssetVersion.asset_seq, AssetVersion.version
    )
    assert [(v.asset_seq, v.version, v.note, v.created_at) for v in versions] == [
        (made.asset, made.version, made.note, made.when) for made in VERSIONS
    ]
    files = await rows(
        session, AssetFile, AssetFile.asset_seq, AssetFile.version, AssetFile.path
    )
    assert [
        (f.asset_seq, f.version, f.path, f.media_type, f.bytes, f.created_at)
        for f in files
    ] == [
        (made.asset, made.version, *file, made.when)
        for made in VERSIONS
        for file in sorted(made.files)
    ]
    for file in files:
        assert len(media.read(file.asset_seq, file.version, file.path)) == file.bytes


async def test_claims_and_evidence_follow_every_version(session, seeded):
    claims = await rows(
        session,
        AssetClaim,
        AssetClaim.asset_seq,
        AssetClaim.version,
        AssetClaim.verified.desc(),
        AssetClaim.text,
    )
    expected = []
    for made in VERSIONS:
        expected += sorted(
            (made.asset, made.version, text, "proof", ref, True) for text, ref in PROOF
        )
        if ASSETS[made.asset - 1]["status"] == "held":
            expected.append((made.asset, made.version, *HELD))
    assert [
        (c.asset_seq, c.version, c.text, c.source_kind, c.source_ref, c.verified)
        for c in claims
    ] == expected
    evidence = await rows(
        session,
        AssetEvidence,
        AssetEvidence.asset_seq,
        AssetEvidence.version,
        AssetEvidence.ref,
    )
    assert [(e.asset_seq, e.version, e.kind, e.ref, e.detail) for e in evidence] == [
        (made.asset, made.version, "brand", ref, detail)
        for made in VERSIONS
        for ref, detail in EVIDENCE
    ]


async def test_runs_and_tool_calls_record_how_each_version_was_made(session, seeded):
    runs = await rows(session, SkillRun, SkillRun.seq)
    found = [
        (
            r.skill,
            r.skill_sha,
            r.caller,
            r.asset_seq,
            r.version,
            r.stage,
            r.status,
            r.error,
            r.model,
            r.tokens_in,
            r.tokens_out,
            r.duration_ms,
            r.started_at,
            r.finished_at,
        )
        for r in runs
    ]
    expected = []
    for made in VERSIONS:
        spec = ASSETS[made.asset - 1]
        started = made.when - timedelta(milliseconds=made.duration_ms)
        expected.append(
            (
                spec["skill"],
                catalog.load(spec["skill"]).sha,
                spec["origin"],
                made.asset,
                made.version,
                None,
                spec["status"],
                None,
                MODEL,
                made.tokens_in,
                made.tokens_out,
                made.duration_ms,
                started,
                made.when,
            )
        )
    assert found == expected
    calls = await rows(
        session, SkillRunToolCall, SkillRunToolCall.skill_run_seq, SkillRunToolCall.tool
    )
    assert [
        (c.skill_run_seq, c.tool, c.ok, c.duration_ms, c.detail) for c in calls
    ] == [
        (run.seq, tool, True, made.call_ms, detail)
        for run, made in zip(runs, VERSIONS, strict=True)
        for tool, detail in made.tools
    ]


async def test_calendar_state_and_thread_sit_beside_the_library(session, seeded):
    [agent] = await rows(session, AgentRun, AgentRun.seq)
    assert (
        agent.agent,
        agent.trigger,
        agent.read_detail,
        agent.made,
        agent.duration_ms,
        agent.ok,
        agent.error,
        agent.created_at,
    ) == ("marketer", "daily", "6 slots, 2 empty", 2, 84000, True, None, at(9, 3, 6))
    [skip] = await rows(session, SlotSkip, SlotSkip.slot_date)
    today = NOW.date()
    upcoming = declared.dates(
        declared.slots()["linkedin_post"],
        today + timedelta(days=1),
        today + timedelta(days=14),
    )
    assert (skip.slot_date, skip.slot_name, skip.created_at) == (
        upcoming[0],
        "linkedin_post",
        at(9, 3, 12),
    )
    [thread] = await rows(session, StudioThread, StudioThread.seq)
    assert (thread.title, thread.created_at) == (
        "a post on the coverage gate",
        at(9, 2, 9, 55),
    )
    post_run = await session.scalar(
        select(SkillRun.seq).where(SkillRun.asset_seq == 5, SkillRun.version == 1)
    )
    turns = await rows(session, StudioTurn, StudioTurn.created_at)
    assert [
        (t.thread_seq, t.role, t.text, t.skill_run_seq, t.created_at) for t in turns
    ] == [
        (
            thread.seq,
            "person",
            "Make a post about the coverage gate for the owner, with the image.",
            None,
            at(9, 2, 9, 56),
        ),
        (
            thread.seq,
            "studio",
            "Writing one post on the test gate, with a stat card at 1:1.",
            post_run,
            at(9, 2, 9, 57),
        ),
    ]


async def test_seed_reads_the_manifest_it_is_given_and_rebases_it_to_now(
    session, tmp_path, monkeypatch
):
    fixtures = tmp_path / "library"
    (fixtures / "nine" / "1").mkdir(parents=True)
    (fixtures / "nine" / "1" / "post.md").write_text("Hello")
    (fixtures / "manifest.yaml").write_text(yaml.safe_dump(SMALL))
    monkeypatch.setattr(seed_demo, "STUDIO_FIXTURES", fixtures)
    counts = await seed_demo.seed_studio(session)
    assert counts == {**dict.fromkeys(COUNTS, 1)}
    [asset] = await rows(session, Asset, Asset.seq)
    assert (asset.name, asset.created_at, asset.slot_date, asset.slot_name) == (
        "One number",
        at(9, 4, 9),
        date(2026, 8, 31),
        "linkedin_post",
    )
    [run] = await rows(session, SkillRun, SkillRun.seq)
    assert (run.status, run.started_at, run.finished_at) == (
        "held",
        at(9, 4, 8, 59),
        at(9, 4, 9),
    )
    [thread] = await rows(session, StudioThread, StudioThread.seq)
    [turn] = await rows(session, StudioTurn, StudioTurn.created_at)
    assert (thread.created_at, turn.skill_run_seq, turn.created_at) == (
        at(9, 4, 8, 59),
        run.seq,
        at(9, 4, 9),
    )
    assert media.read(asset.seq, 1, "post.md") == b"Hello"


BRANDS = ("pipedrive", "pied piper", "hubspot", "os.dev")
CALLS = {
    "pricing": "Harbor Lane <> OS — pricing and rollout",
    "renewal": "Blue Kettle — renewal check-in",
    "expansion": "Granite Row — expansion to the growth team",
    "intro": "Pine Street — intro call",
    "security": "Copper Field — security review",
    "billing": "River Bend — billing escalation",
}
TRANSCRIPT = (
    "We have been doing the pricing by hand every quarter and it takes a week. "
    "The security compliance questions come from our customers, not from us. "
    "We would want to decide inside the next three months if the numbers hold."
)

REP_AND_PROSPECT = (
    "Ines Duarte (Acme Dental): Our group pricing starts at forty seats and covers "
    "everyone.\n"
    "Sam Okafor: The pricing for forty people is more than we budgeted this year."
)


def test_the_rep_is_whoever_speaks_under_an_affiliation_whatever_it_names():
    assert seed_demo.sentence(REP_AND_PROSPECT, "pricing") == (
        "The pricing for forty people is more than we budgeted this year."
    )


def test_with_no_affiliated_speaker_every_line_is_read():
    plain = REP_AND_PROSPECT.replace(" (Acme Dental)", "")
    assert seed_demo.sentence(plain, "pricing") == (
        "Our group pricing starts at forty seats and covers everyone."
    )


def test_the_seed_names_no_brand():
    for text in (Path(seed_demo.__file__).read_text(), seed_demo.SEED.read_text()):
        for brand in BRANDS:
            assert brand not in text.lower()


async def test_meetings_and_briefings_take_company_names_from_the_database(
    session, canonical
):
    meetings = {
        topic: await canonical("meeting", {"name": name, "transcript": TRANSCRIPT})
        for topic, name in CALLS.items()
    }
    read = await seed_demo.seed_meetings(session, "vocabulary-sha")
    calls = seed_demo.read_seed()["calls"]
    assert read == sum(2 + len(call["pain_points"]) for call in calls)
    labels = await session.execute(
        select(EnrichedFact.attr, EnrichedFact.value).where(
            EnrichedFact.canonical_id == meetings["security"]
        )
    )
    assert set(labels.all()) == {
        ("interest", "moderate"),
        ("timing", "next_quarter"),
        ("pain_points", "security_compliance"),
        ("pain_points", "integration_complexity"),
    }
    await seed_demo.seed_briefings(session)
    briefs = await rows(session, BriefingRun, BriefingRun.created_at)
    said = " ".join(brief.briefing for brief in briefs)
    assert all(name.split(" <> ")[0].split(" — ")[0] in said for name in CALLS.values())
    assert not any(brand in said.lower() for brand in BRANDS)
    findings = {
        finding["entity"]
        for brief in briefs
        for finding in brief.read_manifest["findings"]
    }
    assert findings == {"River Bend", "Pine Street", "Blue Kettle"}


def look_alike(pair: str, decided: str | None, number: int) -> dict:
    return {
        "pair": pair,
        "decided": decided,
        "records": [
            {
                "source": "zendesk",
                "object_type": "users",
                "source_id": f"3900{number}",
                "fields": {
                    "name": f"{pair.title()} Ruiz",
                    "phone": f"+1415555019{number}",
                },
            },
            {
                "source": "intercom",
                "object_type": "contacts",
                "source_id": f"con_{pair}",
                "fields": {
                    "name": f"{pair[0].upper()} Ruiz",
                    "phone": f"+1 415 555 019{number}",
                },
            },
        ],
    }


SMALL_SEED = {
    "calls": [
        {
            "key": "kickoff",
            "interest": "weak",
            "timing": "no_timeline",
            "pain_points": ["performance"],
            "verified": True,
        }
    ],
    "tickets": [{"subject": "Locked out", "complaint": "access"}],
    "briefings": {
        "ceo": {
            "history": ["Nothing was read before {kickoff} called."],
            "latest": "{kickoff} is weak, and {kickoff} names no date.",
        },
        "head_of_sales": {"history": [], "latest": "Plain words and no braces."},
    },
    "read": {
        "metrics": {"mrr": 1.0},
        "goals": {
            "mrr_target": {"target": 2, "current": 1.0, "met": False},
            "deals_with_next_step": {"target": None, "current": None, "met": True},
        },
        "findings": [{"rule": "stale_deal", "call": "kickoff"}],
    },
    "lookalikes": [look_alike("ana", "confirmed", 1), look_alike("ben", None, 2)],
}
SMALL_MANIFEST = {
    "metrics": {"mrr": 1.0},
    "goals": {
        "mrr_target": {"target": 2, "current": 1.0, "met": False},
        "deals_with_next_step": {"met": True},
    },
    "findings": [{"rule": "stale_deal", "entity": "Harbor Lane"}],
}


@pytest.fixture
def small_seed(tmp_path, monkeypatch):
    path = tmp_path / "seed.yaml"
    path.write_text(yaml.safe_dump(SMALL_SEED, sort_keys=False))
    monkeypatch.setattr(seed_demo, "SEED", path)


async def test_meetings_tickets_and_briefings_follow_the_seed_file(
    session, canonical, small_seed
):
    kickoff = await canonical(
        "meeting", {"name": "Harbor Lane — kickoff", "transcript": TRANSCRIPT}
    )
    await canonical("meeting", {"name": CALLS["renewal"], "transcript": TRANSCRIPT})
    locked = await canonical("ticket", {"subject": "Locked out after the update"})
    await canonical("ticket", {"subject": "Billing discrepancy on June invoice"})
    assert await seed_demo.seed_meetings(session, "vocabulary-sha") == 3
    assert await seed_demo.seed_tickets(session, "vocabulary-sha") == 1
    labels = await session.execute(
        select(EnrichedFact.canonical_id, EnrichedFact.attr, EnrichedFact.value)
    )
    assert set(labels.all()) == {
        (kickoff, "interest", "weak"),
        (kickoff, "timing", "no_timeline"),
        (kickoff, "pain_points", "performance"),
        (locked, "complaint", "access"),
    }
    assert await seed_demo.seed_briefings(session) == 3
    briefs = await rows(session, BriefingRun, BriefingRun.role, BriefingRun.created_at)
    assert [(b.role, b.briefing, b.read_manifest) for b in briefs] == [
        ("ceo", "Nothing was read before Harbor Lane called.", SMALL_MANIFEST),
        ("ceo", "Harbor Lane is weak, and Harbor Lane names no date.", SMALL_MANIFEST),
        ("head_of_sales", "Plain words and no braces.", SMALL_MANIFEST),
    ]


async def test_look_alikes_and_their_decisions_follow_the_seed_file(
    session, small_seed
):
    assert await seed_demo.seed_candidates(session) == 2
    candidates = await rows(session, MergeCandidate, MergeCandidate.left_anchor)
    assert [
        (c.left_anchor, c.right_anchor, c.status, c.decided_at) for c in candidates
    ] == [
        ("intercom|person|con_ana", "zendesk|person|39001", "confirmed", at(9, 4, 9)),
        ("intercom|person|con_ben", "zendesk|person|39002", "pending", None),
    ]


async def seed_the_template(session, canonical) -> None:
    world = ground_truth.world()
    await seed_demo.seed_candidates(session)
    for call in world.SALES_CALLS:
        said = "\n".join(f"{speaker}: {line}" for speaker, line in call.transcript)
        await canonical("meeting", {"name": call.topic, "transcript": said})
    for ticket in world.TICKETS:
        await canonical("ticket", {"subject": ticket.subject})
    await seed_demo.seed_meetings(session, "vocabulary-sha")
    await seed_demo.seed_tickets(session, "vocabulary-sha")
    await seed_demo.seed_briefings(session)
    await session.flush()


FACT_COLUMNS = ("reading", "attr", "value", "quote", "quote_verified", "created_at")


def written(row, *columns) -> dict:
    values = {column: getattr(row, column) for column in columns}
    return {
        column: value.isoformat() if isinstance(value, datetime) else value
        for column, value in values.items()
    }


async def seeded_rows(session) -> dict:
    named = dict(
        (
            await session.execute(
                select(FactCurrent.canonical_id, FactCurrent.value).where(
                    FactCurrent.attr.in_(("name", "subject"))
                )
            )
        ).all()
    )
    briefings = await rows(session, BriefingRun, BriefingRun.seq)
    facts = await rows(
        session,
        EnrichedFact,
        EnrichedFact.reading,
        EnrichedFact.created_at.desc(),
        EnrichedFact.attr,
        EnrichedFact.value,
    )
    runs = await rows(session, EnrichmentRun, EnrichmentRun.reading)
    candidates = await rows(
        session, MergeCandidate, MergeCandidate.left_anchor, MergeCandidate.right_anchor
    )
    return {
        "briefing_run": [
            written(b, "role", "briefing", "read_manifest", "duration_ms", "created_at")
            for b in briefings
        ],
        "enriched_fact": [
            {"of": named[f.canonical_id], **written(f, *FACT_COLUMNS)} for f in facts
        ],
        "enrichment_run": [written(r, "reading", "read", "created_at") for r in runs],
        "merge_candidate": [
            written(c, "left_anchor", "right_anchor", "status", "decided_at")
            for c in candidates
        ],
    }


@pytest.mark.skipif(
    not (Path(ground_truth.ADVERSARIAL_ROOT) / "seeds" / "world").is_dir(),
    reason="the mock is not mounted at ADVERSARIAL_ROOT",
)
async def test_seeding_the_template_writes_the_rows_it_always_has(session, canonical):
    await seed_the_template(session, canonical)
    assert await seeded_rows(session) == json.loads(SEEDED.read_text())


CUSTOM_APPS = (
    "batch_trace",
    "check_deposits",
    "damage_claims",
    "equipment_checkout",
    "event_check_in",
    "field_service_report",
    "food_safety_log",
    "inventory_count",
    "mailroom",
    "maintenance_tags",
    "mileage_log",
    "perio_charting",
    "property_inspection",
    "proof_of_delivery",
    "receipts",
    "sales_visit_debrief",
    "shelf_audit",
    "site_safety_walk",
    "supplier_invoices",
    "vehicle_pre_trip",
    "vet_visit_notes",
)
MONEY_APPS = {
    "check_deposits",
    "damage_claims",
    "receipts",
    "shelf_audit",
    "supplier_invoices",
}
VOICE_APPS = {
    "field_service_report",
    "food_safety_log",
    "perio_charting",
    "property_inspection",
    "sales_visit_debrief",
    "site_safety_walk",
    "vehicle_pre_trip",
    "vet_visit_notes",
}
TEMPLATE_APPS = {"perio_charting", "property_inspection", "vehicle_pre_trip"}
PRE_TRIP = (
    "service_brakes",
    "parking_brake",
    "steering",
    "lights_and_reflectors",
    "tires",
    "horn",
    "wipers",
    "mirrors",
    "coupling_devices",
    "wheels_and_rims",
    "emergency_equipment",
)
RECEIPT_ID = "0b9a6b8e-3c1f-4d2a-9e57-2f4c1d7a0001"
CHECK_ID = "0b9a6b8e-3c1f-4d2a-9e57-2f4c1d7a0002"
HARBOR_FUEL_JPEG = b"\xff\xd8\xff\xe0 harbor fuel"
HARBOR_FUEL = {
    "vendor": "Harbor Fuel",
    "total": 48.2,
    "category": "fuel",
    "date": "2026-09-03",
}
TIRES = {"vehicle:tires": {"result": "fail", "defect": "Front left tread low"}}
SMALL_RECORDS = {
    "records": [
        {
            "id": RECEIPT_ID,
            "app": "receipts",
            "recorded_at": "2026-09-03T17:40:00Z",
            "saved_at": "2026-09-03T17:42:00Z",
            "files": [{"path": "harbor-fuel.jpg", "kind": "photo"}],
            "fields": HARBOR_FUEL,
        },
        {
            "id": CHECK_ID,
            "app": "vehicle_pre_trip",
            "recorded_at": "2026-09-04T06:10:00Z",
            "saved_at": "2026-09-04T06:15:00Z",
            "transcript": "tires fail, front left tread low",
            "fields": {"vehicle": "Truck 7"},
            "template": {"items": TIRES},
        },
    ]
}


def custom_entries() -> list[dict]:
    path = seed_demo.CUSTOM_FIXTURES / "records.yaml"
    return yaml.safe_load(path.read_text())["records"]


def custom_sample(path: str) -> bytes:
    return (seed_demo.CUSTOM_FIXTURES / "samples" / path).read_bytes()


def custom_files(entry: dict) -> list[dict]:
    return sorted(entry.get("files", []), key=lambda file: file["path"])


def moment(value) -> datetime:
    when = datetime.fromisoformat(value) if isinstance(value, str) else value
    return when if when.tzinfo else when.replace(tzinfo=UTC)


def zulu(value) -> str:
    return moment(value).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def as_json(value):
    return json.loads(json.dumps(value, default=str))


def pick(fields: dict, *names: str) -> dict:
    return {name: fields.get(name) for name in names}


def seeded_payload(entry: dict) -> dict:
    payload = {
        "record": str(entry["id"]),
        "app": entry["app"],
        "recorded_at": zulu(entry["recorded_at"]),
        "recorded_by": "admin",
        "removed": False,
        "files": [
            {
                "path": file["path"],
                "media_type": media.media_type(file["path"]),
                "kind": file["kind"],
            }
            for file in custom_files(entry)
        ],
        "fields": as_json(entry["fields"]),
    }
    if entry["app"] in MONEY_APPS:
        payload["currency"] = "USD"
    if entry["app"] in VOICE_APPS:
        payload["transcript"] = entry.get("transcript")
    if entry["app"] in TEMPLATE_APPS:
        empty = {"rows": {}, "cells": {}, "items": {}}
        payload["template"] = {**empty, **as_json(entry.get("template", {}))}
    return payload


@pytest_asyncio.fixture
async def seeded_custom(session):
    counts = await seed_demo.seed_custom(session)
    await session.flush()
    return counts


@pytest.fixture
def small_records(tmp_path, monkeypatch):
    fixtures = tmp_path / "custom"
    (fixtures / "samples").mkdir(parents=True)
    (fixtures / "samples" / "harbor-fuel.jpg").write_bytes(HARBOR_FUEL_JPEG)
    (fixtures / "records.yaml").write_text(
        yaml.safe_dump(SMALL_RECORDS, sort_keys=False)
    )
    monkeypatch.setattr(seed_demo, "CUSTOM_FIXTURES", fixtures)


async def custom_payloads(session, app_name: str) -> list[dict]:
    payloads = await session.execute(
        select(RawEvent.raw_payload)
        .where(RawEvent.source == "custom", RawEvent.object_type == app_name)
        .order_by(RawEvent.seq)
    )
    return list(payloads.scalars())


async def custom_events(session) -> list:
    return [
        e for e in await rows(session, RawEvent, RawEvent.seq) if e.source == "custom"
    ]


def test_the_custom_records_file_lists_two_saved_records_for_each_app():
    apps_listed = Counter(entry["app"] for entry in custom_entries())
    assert apps_listed == dict.fromkeys(CUSTOM_APPS, 2)


def test_each_custom_record_has_its_own_id():
    ids = {str(uuid.UUID(str(entry["id"]))) for entry in custom_entries()}
    assert len(ids) == len(custom_entries())


def test_each_custom_record_was_saved_after_it_was_recorded():
    late = [
        entry["id"]
        for entry in custom_entries()
        if moment(entry["saved_at"]) <= moment(entry["recorded_at"])
    ]
    assert late == []


def test_every_custom_sample_has_the_bytes_its_name_promises():
    wrong = [
        file["path"]
        for entry in custom_entries()
        for file in custom_files(entry)
        if media.sniff(custom_sample(file["path"])) != media.media_type(file["path"])
    ]
    assert wrong == []


def test_the_custom_samples_hold_a_photo_a_pdf_a_clip_and_a_signature():
    kinds = {file["kind"] for entry in custom_entries() for file in custom_files(entry)}
    assert kinds == {"photo", "pdf", "audio", "signature"}


async def test_seed_custom_counts_what_it_wrote(seeded_custom):
    files = sum(len(custom_files(entry)) for entry in custom_entries())
    assert seeded_custom == {
        "custom_record": 42,
        "custom_record_file": files,
        "custom_record_audit": 84,
    }


async def test_seeded_custom_records_keep_their_ids_and_pinned_times(
    session, seeded_custom
):
    found = await rows(session, models.CustomRecord, models.CustomRecord.id)
    assert sorted(
        (str(r.id), r.app, r.recorded_by, r.created_at, r.saved_at, r.removed_at)
        for r in found
    ) == sorted(
        (
            str(e["id"]),
            e["app"],
            "admin",
            moment(e["recorded_at"]),
            moment(e["saved_at"]),
            None,
        )
        for e in custom_entries()
    )


async def test_seeded_custom_times_do_not_follow_the_clock(session, monkeypatch):
    later = NOW + timedelta(days=30)
    monkeypatch.setattr(seed_demo, "NOW", later)
    monkeypatch.setattr(settings, "CLOCK_PINNED_AT", later)
    await seed_demo.seed_custom(session)
    found = await rows(session, models.CustomRecord, models.CustomRecord.id)
    assert sorted((str(r.id), r.created_at) for r in found) == sorted(
        (str(e["id"]), moment(e["recorded_at"])) for e in custom_entries()
    )


async def test_each_seeded_custom_record_is_one_raw_event_of_the_custom_source(
    session, seeded_custom
):
    events = await custom_events(session)
    assert len(events) == len(custom_entries())
    assert {(e.object_type, e.source_id): e.raw_payload for e in events} == {
        (entry["app"], str(entry["id"])): seeded_payload(entry)
        for entry in custom_entries()
    }


async def test_seeded_custom_files_are_rows_beside_their_record(session, seeded_custom):
    files = await rows(session, models.CustomRecordFile, models.CustomRecordFile.path)
    assert sorted(
        (str(f.record_id), f.path, f.media_type, f.bytes, f.kind, f.created_at)
        for f in files
    ) == sorted(
        (
            str(e["id"]),
            file["path"],
            media.media_type(file["path"]),
            len(custom_sample(file["path"])),
            file["kind"],
            moment(e["recorded_at"]),
        )
        for e in custom_entries()
        for file in custom_files(e)
    )


async def test_seeded_custom_files_are_written_to_the_record_store(
    session, seeded_custom
):
    files = await rows(session, models.CustomRecordFile, models.CustomRecordFile.path)
    unwritten = [
        f.path
        for f in files
        if media.read_record(f.record_id, f.path) != custom_sample(f.path)
    ]
    assert unwritten == []


async def test_each_seeded_custom_record_was_created_then_saved_by_admin(
    session, seeded_custom
):
    notes = await rows(session, models.CustomRecordAudit, models.CustomRecordAudit.at)
    by_record: dict[str, list] = {}
    for note in notes:
        by_record.setdefault(str(note.record_id), []).append(
            (note.action, note.actor, note.at)
        )
    assert by_record == {
        str(e["id"]): [
            ("create", "admin", moment(e["recorded_at"])),
            ("save", "admin", moment(e["saved_at"])),
        ]
        for e in custom_entries()
    }


async def test_seeding_custom_records_calls_no_model(session, monkeypatch):
    async def refuse(*args, **kwargs):
        raise AssertionError("the seed called a model")

    monkeypatch.setattr(settings, "CUSTOM_ENABLED", True)
    monkeypatch.setattr(settings, "TRANSCRIBE_ENABLED", True)
    monkeypatch.setattr(llm, "parse", refuse)
    monkeypatch.setattr("app.custom.reader.read", refuse)
    monkeypatch.setattr("app.custom.transcribe.transcribe", refuse)
    counts = await seed_demo.seed_custom(session)
    assert counts["custom_record"] == len(custom_entries())


async def test_seeding_custom_records_twice_leaves_one_copy(session):
    first = await seed_demo.seed_custom(session)
    await session.flush()
    assert await seed_demo.seed_custom(session) == first
    await session.flush()
    found = await rows(session, models.CustomRecord, models.CustomRecord.id)
    assert (len(found), len(await custom_events(session))) == (42, 42)


async def test_the_seeded_harbor_fuel_receipt_is_48_20_of_diesel(
    session, seeded_custom
):
    fuel = next(
        p
        for p in await custom_payloads(session, "receipts")
        if p["fields"].get("vendor") == "Harbor Fuel"
    )
    assert pick(fuel["fields"], "total", "category", "date", "items") == {
        "total": 48.2,
        "category": "fuel",
        "date": "2026-09-03",
        "items": [{"description": "Diesel", "amount": 48.2}],
    }
    assert fuel["currency"] == "USD"


async def test_the_seeded_northside_office_supply_receipt_is_12_of_supplies(
    session, seeded_custom
):
    supply = next(
        p
        for p in await custom_payloads(session, "receipts")
        if p["fields"].get("vendor") == "Northside Office Supply"
    )
    assert pick(supply["fields"], "total", "category", "date") == {
        "total": 12.0,
        "category": "supplies",
        "date": "2026-09-02",
    }
    assert supply["currency"] == "USD"


async def test_the_seeded_check_out_is_laptop_lap_014(session, seeded_custom):
    found = [
        pick(p["fields"], "asset", "action")
        for p in await custom_payloads(session, "equipment_checkout")
    ]
    assert {"asset": "LAP-014", "action": "check_out"} in found


async def test_the_seeded_maintenance_tag_is_press_02s_new_seal(session, seeded_custom):
    found = [
        pick(p["fields"], "asset", "work_done", "status", "next_service")
        for p in await custom_payloads(session, "maintenance_tags")
    ]
    assert {
        "asset": "PRESS-02",
        "work_done": "Replaced hydraulic seal",
        "status": "working",
        "next_service": "2026-10-01",
    } in found


async def test_the_seeded_food_safety_log_opens_with_the_walk_in_and_the_freezer(
    session, seeded_custom
):
    found = [
        (
            p["fields"].get("shift"),
            [(r.get("unit"), r.get("temperature")) for r in p["fields"]["readings"]],
        )
        for p in await custom_payloads(session, "food_safety_log")
    ]
    assert ("opening", [("walk_in_cooler", 37), ("freezer", -2)]) in found


async def test_the_seeded_perio_chart_is_jordan_riveras_tooth_3(session, seeded_custom):
    chart = next(
        p
        for p in await custom_payloads(session, "perio_charting")
        if p["fields"].get("patient") == "Jordan Rivera"
    )
    cells = chart["template"]["cells"]
    assert (
        chart["fields"]["exam_date"],
        [cells[f"3:{site}"]["depth"] for site in ("DB", "B", "MB")],
    ) == ("2026-09-02", [3, 2, 4])


async def test_the_seeded_pre_trip_check_fails_truck_7s_tires_only(
    session, seeded_custom
):
    check = next(
        p
        for p in await custom_payloads(session, "vehicle_pre_trip")
        if p["fields"].get("vehicle") == "Truck 7"
    )
    items = check["template"]["items"]
    assert {key: item["result"] for key, item in items.items()} == {
        f"vehicle:{item}": "fail" if item == "tires" else "pass" for item in PRE_TRIP
    }
    assert items["vehicle:tires"]["defect"] == "Front left tread low"


async def test_the_seeded_delivery_is_order_1042_signed_by_jordan_rivera(
    session, seeded_custom
):
    delivery = next(
        p
        for p in await custom_payloads(session, "proof_of_delivery")
        if p["fields"].get("order_number") == "1042"
    )
    assert pick(delivery["fields"], "customer", "signed_by", "condition") == {
        "customer": "Jordan Rivera",
        "signed_by": "Jordan Rivera",
        "condition": "good",
    }


async def test_the_seeded_delivery_carries_a_signature_file(session, seeded_custom):
    delivery = next(
        p
        for p in await custom_payloads(session, "proof_of_delivery")
        if p["fields"].get("order_number") == "1042"
    )
    assert [f["media_type"] for f in delivery["files"] if f["kind"] == "signature"] == [
        "image/png"
    ]


async def test_seed_custom_counts_the_records_file_it_is_given(session, small_records):
    assert await seed_demo.seed_custom(session) == {
        "custom_record": 2,
        "custom_record_file": 1,
        "custom_record_audit": 4,
    }


async def test_seed_custom_writes_the_payloads_a_save_would(session, small_records):
    await seed_demo.seed_custom(session)
    events = await rows(session, RawEvent, RawEvent.source_id)
    assert [(e.source, e.object_type, e.source_id, e.raw_payload) for e in events] == [
        (
            "custom",
            "receipts",
            RECEIPT_ID,
            {
                "record": RECEIPT_ID,
                "app": "receipts",
                "recorded_at": "2026-09-03T17:40:00Z",
                "recorded_by": "admin",
                "removed": False,
                "currency": "USD",
                "files": [
                    {
                        "path": "harbor-fuel.jpg",
                        "media_type": "image/jpeg",
                        "kind": "photo",
                    }
                ],
                "fields": HARBOR_FUEL,
            },
        ),
        (
            "custom",
            "vehicle_pre_trip",
            CHECK_ID,
            {
                "record": CHECK_ID,
                "app": "vehicle_pre_trip",
                "recorded_at": "2026-09-04T06:10:00Z",
                "recorded_by": "admin",
                "removed": False,
                "transcript": "tires fail, front left tread low",
                "files": [],
                "fields": {"vehicle": "Truck 7"},
                "template": {"rows": {}, "cells": {}, "items": TIRES},
            },
        ),
    ]


async def test_seed_custom_stores_the_sample_it_is_given(session, small_records):
    await seed_demo.seed_custom(session)
    assert (
        media.read_record(uuid.UUID(RECEIPT_ID), "harbor-fuel.jpg") == HARBOR_FUEL_JPEG
    )
