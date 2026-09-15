import sys
import types
from datetime import UTC, date, datetime

from app import media
from app.config import settings
from app.models import (
    AgentRun,
    Asset,
    AssetFile,
    EnrichedFact,
    Proposal,
    ProposalClaim,
    ProposalDraft,
    ProposalEvidence,
    RawEvent,
    SkillRun,
    SkillRunToolCall,
    SlotSkip,
    SyncRun,
)

NOW = datetime(2026, 9, 4, 12, tzinfo=UTC)
TODAY = NOW.date()


async def add(session, row):
    session.add(row)
    await session.flush()
    return row


async def proposal(session, **kw):
    fields = {
        "kind": "post",
        "title": "Three tools, one Acme",
        "skill": "dw-post",
        "skill_sha": "a3f9",
        "status": "open",
        "created_at": NOW,
        **kw,
    }
    return await add(session, Proposal(**fields))


async def evidence(
    session, seq, kind="brand", ref="brand/voice.md", detail="the voice"
):
    return await add(
        session,
        ProposalEvidence(proposal_seq=seq, kind=kind, ref=ref, detail=detail),
    )


async def claim(
    session, seq, text="27 tools", source_kind="proof", source_ref=None, verified=True
):
    return await add(
        session,
        ProposalClaim(
            proposal_seq=seq,
            text=text,
            source_kind=source_kind,
            source_ref=source_ref,
            verified=verified,
        ),
    )


async def draft(session, seq, path="post.md", media_type="text/markdown", size=12):
    return await add(
        session,
        ProposalDraft(proposal_seq=seq, path=path, media_type=media_type, bytes=size),
    )


async def asset(session, **kw):
    fields = {
        "name": "three-tools",
        "kind": "post",
        "origin": "proposal",
        "created_at": NOW,
        **kw,
    }
    return await add(session, Asset(**fields))


async def asset_file(
    session,
    seq,
    version=1,
    path="post.md",
    media_type="text/markdown",
    size=12,
    note=None,
    created_at=NOW,
):
    return await add(
        session,
        AssetFile(
            asset_seq=seq,
            version=version,
            path=path,
            media_type=media_type,
            bytes=size,
            note=note,
            created_at=created_at,
        ),
    )


async def skill_run(session, **kw):
    fields = {
        "skill": "dw-post",
        "skill_sha": "a3f9",
        "mode": "draft",
        "caller": "studio",
        "status": "ok",
        "duration_ms": 41,
        "cost_usd": 0,
        "started_at": NOW,
        **kw,
    }
    return await add(session, SkillRun(**fields))


async def tool_call(
    session, run_seq, tool="brand.read", ok=True, duration_ms=3, detail=None
):
    return await add(
        session,
        SkillRunToolCall(
            skill_run_seq=run_seq,
            tool=tool,
            ok=ok,
            duration_ms=duration_ms,
            detail=detail,
        ),
    )


async def agent_run(session, **kw):
    fields = {
        "agent": "marketer",
        "trigger": "daily",
        "read_detail": "four brand files, nine ads",
        "proposed": 2,
        "duration_ms": 900,
        "cost_usd": 0,
        "ok": True,
        "created_at": NOW,
        **kw,
    }
    return await add(session, AgentRun(**fields))


async def slot_skip(session, slot_date, slot_name):
    return await add(
        session, SlotSkip(slot_date=slot_date, slot_name=slot_name, created_at=NOW)
    )


async def sync_run(
    session, source, ok=True, rows_written=3, detail=None, started_at=NOW
):
    return await add(
        session,
        SyncRun(
            source=source,
            ok=ok,
            rows_written=rows_written,
            detail=detail,
            started_at=started_at,
        ),
    )


def media_at(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "MEDIA_DIR", str(tmp_path))
    return tmp_path


def store_file(kind, seq, version, path, data):
    return media.write(kind, seq, version, path, data)


def studio_on(monkeypatch):
    monkeypatch.setattr(settings, "STUDIO_ENABLED", True)


class FakeMarketer:
    def __init__(self):
        self.calls: list = []

    async def fill(self, session, days):
        self.calls.append(days)
        return types.SimpleNamespace(seq=9)


def fake_marketer(monkeypatch):
    marketer = FakeMarketer()
    module = types.ModuleType("app.agents.marketer")
    module.fill = marketer.fill
    monkeypatch.setitem(sys.modules, "app.agents.marketer", module)
    return marketer


async def enriched(
    session,
    canonical_id,
    attr="angle",
    value="approval",
    quote="You approve every ad",
    reading="competitor_creative",
    entity_type="competitor_ad",
):
    return await add(
        session,
        EnrichedFact(
            canonical_id=canonical_id,
            entity_type=entity_type,
            reading=reading,
            attr=attr,
            value=value,
            quote=quote,
            quote_verified=True,
            input_sha="a3f9",
            vocabulary_sha="0c7a",
            model="claude-test",
            prompt_version="2026-09-01.1",
        ),
    )


async def raw_event(session, source, object_type, source_id, payload=None):
    return await add(
        session,
        RawEvent(
            source=source,
            object_type=object_type,
            source_id=source_id,
            raw_payload=payload or {},
            payload_sha="a3f9",
        ),
    )


def day(offset):
    return date.fromordinal(TODAY.toordinal() + offset)
