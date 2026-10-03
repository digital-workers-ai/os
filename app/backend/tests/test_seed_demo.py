import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import NamedTuple

import pytest
import pytest_asyncio
import yaml
from sqlalchemy import select

from app import media
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
