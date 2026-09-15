from datetime import timedelta

from sqlalchemy import select

from app import clock
from app.engine import brand
from app.engine import calendar as spec
from app.engine import competitors as company
from app.models import AgentRun, Asset, Proposal, SkillRun, SyncRun
from app.studio import calendar, proposals

OPEN = 10

NOTICED_DAYS = 7

NOTICED = 5


def agent_run_row(run):
    return {
        "seq": run.seq,
        "agent": run.agent,
        "trigger": run.trigger,
        "read_detail": run.read_detail,
        "proposed": run.proposed,
        "duration_ms": run.duration_ms,
        "cost_usd": float(run.cost_usd),
        "ok": run.ok,
        "error": run.error,
        "created_at": run.created_at.isoformat(),
    }


def skill_run_row(run):
    return {
        "seq": run.seq,
        "skill": run.skill,
        "model": run.model or "",
        "tokens_in": run.tokens_in,
        "tokens_out": run.tokens_out,
        "mode": run.mode,
        "caller": run.caller,
        "proposal_seq": run.proposal_seq,
        "asset_seq": run.asset_seq,
        "stage": run.stage,
        "status": run.status,
        "error": run.error,
        "duration_ms": run.duration_ms,
        "cost_usd": float(run.cost_usd),
        "started_at": run.started_at.isoformat(),
        "finished_at": None if run.finished_at is None else run.finished_at.isoformat(),
    }


async def _readiness(session):
    landed = (
        (
            await session.execute(
                select(SyncRun.source).where(SyncRun.rows_written > 0).limit(1)
            )
        )
        .scalars()
        .first()
    )
    return {
        "brand": set(brand.REQUIRED) <= set(brand.files()),
        "competitors": bool(company.tracked()),
        "calendar": bool(spec.slots()),
        "estate": landed is not None,
    }


async def today(session):
    now = clock.now()
    day = now.date()
    monday = day - timedelta(days=day.weekday())
    last_run = (
        (await session.execute(select(AgentRun).order_by(AgentRun.seq.desc()).limit(1)))
        .scalars()
        .first()
    )
    noticed = (
        (
            await session.execute(
                select(Proposal)
                .where(
                    Proposal.reactive,
                    Proposal.created_at >= now - timedelta(days=NOTICED_DAYS),
                )
                .order_by(Proposal.seq.desc())
                .limit(NOTICED)
            )
        )
        .scalars()
        .all()
    )
    building = (
        (
            await session.execute(
                select(SkillRun)
                .where(SkillRun.status == "running")
                .order_by(SkillRun.seq.desc())
            )
        )
        .scalars()
        .all()
    )
    built = (
        (
            await session.execute(
                select(Asset)
                .where(
                    Asset.created_at
                    >= now.replace(hour=0, minute=0, second=0, microsecond=0)
                )
                .order_by(Asset.seq.desc())
            )
        )
        .scalars()
        .all()
    )
    return {
        "today": day.isoformat(),
        "readiness": await _readiness(session),
        "last_run": None if last_run is None else agent_run_row(last_run),
        "open": (await proposals.listing(session, status="open", limit=OPEN))[
            "proposals"
        ],
        "week": await calendar.slots(session, monday, monday + timedelta(days=6)),
        "noticed": [{"text": row.title, "proposal_seq": row.seq} for row in noticed],
        "building": [skill_run_row(row) for row in building],
        "built_today": [
            {"seq": row.seq, "name": row.name, "kind": row.kind} for row in built
        ],
        "skill_proposals": [],
    }
