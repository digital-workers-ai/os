from datetime import timedelta

from sqlalchemy import select

from app import clock
from app.models import AgentRun, Asset, SkillRun
from app.studio import calendar, rows

RUNNING = "running"


async def today(session) -> dict:
    now = clock.now()
    day = now.date()
    monday = day - timedelta(days=day.weekday())
    last = (
        await session.execute(select(AgentRun).order_by(AgentRun.seq.desc()).limit(1))
    ).scalar_one_or_none()
    running = (
        await session.execute(
            select(SkillRun)
            .where(SkillRun.status == RUNNING)
            .order_by(SkillRun.seq.desc())
        )
    ).scalars()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    made = (
        await session.execute(
            select(Asset).where(Asset.created_at >= midnight).order_by(Asset.seq.desc())
        )
    ).scalars()
    return {
        "today": day.isoformat(),
        "last_run": None if last is None else rows.agent_run_row(last),
        "week": await calendar.slots(session, monday, monday + timedelta(days=6)),
        "building": [rows.skill_run_row(run) for run in running],
        "built_today": await rows.asset_rows(session, list(made)),
    }
