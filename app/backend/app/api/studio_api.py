from datetime import date, timedelta
from typing import Annotated

from fastapi import BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field, StringConstraints

from app.api.routers import studio as router
from app.db import get_session
from app.models import Asset
from app.skills import runner
from app.studio import Missing, calendar, canvas, chat, rows

MAX_SPAN = timedelta(days=366)
DEFAULT_FILL_DAYS = 14
MANUAL = "manual"
NOT_FOUND = {404: {"description": "no such thread or slot"}}
CANNOT_RUN = {409: {"description": "the run cannot open"}}


class FillBody(BaseModel):
    days: int = Field(DEFAULT_FILL_DAYS, ge=1, le=90)


class TextBody(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


async def _started(session, started) -> dict:
    asset = await session.get(Asset, started.asset_seq)
    [row] = await rows.asset_rows(session, [asset])
    return {"skill_run": rows.skill_run_row(started.skill_run), "asset": row}


def _schedule(background, started, ask) -> None:
    background.add_task(runner.execute_detached, started.skill_run.seq, ask)


@router.get("/calendar")
async def get_calendar(
    frm: date = Query(alias="from"),
    to: date = Query(),
    session=Depends(get_session),
):
    if to - frm > MAX_SPAN:
        to = frm + MAX_SPAN
    slot_rows = await calendar.slots(session, frm, to)
    return {
        "from": frm.isoformat(),
        "to": to.isoformat(),
        "slots": slot_rows,
        "cadence": calendar.cadence(slot_rows),
    }


@router.post("/calendar/fill")
async def fill_calendar(body: FillBody, session=Depends(get_session)):
    from app.agents import marketer

    run = await marketer.fill(session, body.days, MANUAL)
    await session.commit()
    return {"agent_run": rows.agent_run_row(run)}


@router.post("/slots/{day}/{name}/skip", responses=NOT_FOUND)
async def skip_slot(day: date, name: str, session=Depends(get_session)):
    try:
        await calendar.skip(session, day, name)
    except calendar.SlotError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return {"ok": True}


@router.post("/slots/{day}/{name}/run", responses={**NOT_FOUND, **CANNOT_RUN})
async def run_slot(
    day: date, name: str, background: BackgroundTasks, session=Depends(get_session)
):
    try:
        started, ask = await calendar.run(session, day, name)
    except calendar.UnknownSlot as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (calendar.SlotError, runner.SkillError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    response = await _started(session, started)
    await session.commit()
    _schedule(background, started, ask)
    return response


@router.get("/canvas")
async def get_canvas(
    frm: date | None = Query(None, alias="from"),
    to: date | None = None,
    kind: str | None = None,
    session=Depends(get_session),
):
    return {"nodes": await canvas.nodes(session, frm, to, kind)}


@router.get("/threads")
async def list_threads(session=Depends(get_session)):
    return {"threads": await chat.threads(session)}


@router.post("/threads")
async def create_thread(session=Depends(get_session)):
    thread = await chat.create_thread(session)
    await session.commit()
    return {"thread": chat.thread_row(thread)}


@router.get("/threads/{seq}", responses=NOT_FOUND)
async def get_thread(seq: int, session=Depends(get_session)):
    try:
        return await chat.thread(session, seq)
    except Missing as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/threads/{seq}", responses=NOT_FOUND)
async def send_turn(
    seq: int, body: TextBody, background: BackgroundTasks, session=Depends(get_session)
):
    try:
        outcome = await chat.turn(session, seq, body.text)
    except Missing as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    response = {
        "turn": outcome.turn,
        "reply": outcome.reply,
        "skill_run": None,
        "asset": None,
    }
    if outcome.started is not None:
        response.update(await _started(session, outcome.started))
        _schedule(background, outcome.started, outcome.ask)
    await session.commit()
    return response
