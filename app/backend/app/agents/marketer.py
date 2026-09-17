import logging
import time
from asyncio import sleep
from datetime import date, timedelta

from app import clock
from app.config import settings
from app.db import async_session
from app.models import AgentRun
from app.skills import runner
from app.studio import calendar

WINDOW_DAYS = 14
BUILT = ("ok", "held")

logger = logging.getLogger(__name__)


def _ask(slot) -> runner.Ask:
    return runner.Ask(
        slot["skill"],
        caller="marketer",
        input=slot["theme"],
        look=slot["look"],
        ratio=slot["ratio"],
        slot_date=date.fromisoformat(slot["date"]),
        slot_name=slot["name"],
    )


async def fill(session, days=WINDOW_DAYS, trigger="manual") -> AgentRun:
    started = time.monotonic()
    today = clock.now().date()
    found = await calendar.slots(session, today, today + timedelta(days=days))
    empty = [slot for slot in found if slot["state"] == "empty"]
    made = 0
    errors: list[str] = []
    for slot in empty:
        ask = _ask(slot)
        try:
            opened = await runner.open_run(session, ask)
        except runner.SkillError as exc:
            errors.append(f"{slot['date']} {slot['name']}: {exc}")
            continue
        try:
            result = await runner.execute(session, opened.skill_run, ask)
        except Exception as exc:
            await session.rollback()
            errors.append(f"{type(exc).__name__}: {exc}")
            break
        if result["status"] in BUILT:
            made += 1
    run = AgentRun(
        agent="marketer",
        trigger=trigger,
        read_detail=f"{len(found)} slots, {len(empty)} empty",
        made=made,
        duration_ms=int((time.monotonic() - started) * 1000),
        ok=not errors,
        error="\n".join(errors) or None,
        created_at=clock.now(),
    )
    session.add(run)
    await session.commit()
    return run


def seconds_until(hour, now) -> float:
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def daily() -> None:
    while True:
        await sleep(seconds_until(settings.MARKETER_HOUR, clock.now()))
        try:
            async with async_session() as session:
                await fill(session, trigger="daily")
        except Exception:
            logger.exception("marketer: the daily fill did not finish")
