from datetime import date, timedelta

from fastapi import BackgroundTasks, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from app.api.routers import studio as router
from app.caches import MAX_OFFSET
from app.db import get_session
from app.skills import runner
from app.studio import calendar, canvas, errors, proposals, sources, today

MAX_RANGE_DAYS = 366

MAX_FILL_DAYS = 90

MAX_LAYOUT_NODES = 2000

MAX_FRAMES = 200


class FillBody(BaseModel):
    days: int = Field(14, ge=1, le=MAX_FILL_DAYS)


class DraftBody(BaseModel):
    path: str
    text: str


class ApproveBody(BaseModel):
    variants: list[str] = []


class RejectBody(BaseModel):
    reason: str


class RedoBody(BaseModel):
    note: str


class Position(BaseModel):
    x: float
    y: float


class Frame(BaseModel):
    id: str
    label: str
    nodes: list[str] = []


class LayoutBody(BaseModel):
    layout: dict[str, Position]
    frames: list[Frame] = []


def _missing(exc):
    return HTTPException(404, str(exc))


def _refused(exc):
    return HTTPException(409, str(exc))


@router.get("/today")
async def studio_today(session=Depends(get_session)):
    return await today.today(session)


@router.get("/calendar")
async def studio_calendar(
    frm: date = Query(..., alias="from"),
    to: date = Query(...),
    session=Depends(get_session),
):
    end = min(to, frm + timedelta(days=MAX_RANGE_DAYS))
    slots = await calendar.slots(session, frm, end)
    return {
        "from": frm.isoformat(),
        "to": end.isoformat(),
        "slots": slots,
        "cadence": calendar.cadence(slots),
    }


@router.post("/calendar/fill")
async def fill_calendar(body: FillBody, session=Depends(get_session)):
    run = await calendar.fill(session, body.days)
    await session.commit()
    return {"agent_run": run.seq}


@router.post("/slots/{day}/{name}/skip")
async def skip_slot(day: date, name: str, session=Depends(get_session)):
    await calendar.skip(session, day, name)
    await session.commit()
    return {"ok": True}


@router.get("/proposals")
async def list_proposals(
    status: str | None = None,
    kind: str | None = None,
    slot: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0, le=MAX_OFFSET),
    session=Depends(get_session),
):
    return await proposals.listing(session, status, kind, slot, limit, offset)


@router.get("/proposals/{seq}", responses={404: {"description": "no such proposal"}})
async def read_proposal(seq: int, session=Depends(get_session)):
    try:
        return await proposals.detail(session, seq)
    except errors.Missing as exc:
        raise _missing(exc) from exc


@router.get(
    "/proposals/{seq}/drafts/{path:path}",
    responses={404: {"description": "no such draft"}, 409: {"description": "refused"}},
)
async def read_draft(seq: int, path: str, session=Depends(get_session)):
    try:
        data, media_type = await proposals.draft_bytes(session, seq, path)
    except errors.Missing as exc:
        raise _missing(exc) from exc
    except errors.Refused as exc:
        raise _refused(exc) from exc
    return Response(content=data, media_type=media_type)


@router.put("/proposals/{seq}/draft", responses={404: {"description": "no such draft"}})
async def edit_draft(seq: int, body: DraftBody, session=Depends(get_session)):
    try:
        found = await proposals.edit_draft(session, seq, body.path, body.text)
    except errors.Missing as exc:
        raise _missing(exc) from exc
    await session.commit()
    return found


@router.post(
    "/proposals/{seq}/approve",
    responses={
        404: {"description": "no such proposal"},
        409: {"description": "already decided"},
    },
)
async def approve_proposal(
    seq: int,
    background: BackgroundTasks,
    body: ApproveBody | None = None,
    session=Depends(get_session),
):
    try:
        started = await proposals.approve(session, seq, body.variants if body else [])
    except errors.Missing as exc:
        raise _missing(exc) from exc
    except errors.Refused as exc:
        raise _refused(exc) from exc
    await session.commit()
    background.add_task(runner.execute_detached, started.skill_run, started.ask)
    return {"skill_run": started.skill_run}


@router.post(
    "/proposals/{seq}/reject",
    responses={
        404: {"description": "no such proposal"},
        409: {"description": "already decided"},
    },
)
async def reject_proposal(seq: int, body: RejectBody, session=Depends(get_session)):
    try:
        found = await proposals.reject(session, seq, body.reason)
    except errors.Missing as exc:
        raise _missing(exc) from exc
    except errors.Refused as exc:
        raise _refused(exc) from exc
    await session.commit()
    return found


@router.post(
    "/proposals/{seq}/redo",
    responses={
        404: {"description": "no such proposal"},
        409: {"description": "already decided"},
    },
)
async def redo_proposal(
    seq: int,
    background: BackgroundTasks,
    body: RedoBody,
    session=Depends(get_session),
):
    try:
        started = await proposals.redo(session, seq, body.note)
    except errors.Missing as exc:
        raise _missing(exc) from exc
    except errors.Refused as exc:
        raise _refused(exc) from exc
    await session.commit()
    background.add_task(runner.execute_detached, started.skill_run, started.ask)
    return {"skill_run": started.skill_run}


@router.get("/canvas")
async def read_canvas(
    frm: date | None = Query(None, alias="from"),
    to: date | None = None,
    kind: str | None = None,
    skill: str | None = None,
    session=Depends(get_session),
):
    return await canvas.graph(
        session,
        None if frm is None else frm.isoformat(),
        None if to is None else to.isoformat(),
        kind,
        skill,
    )


@router.put(
    "/canvas/layout", responses={422: {"description": "too large to be a board"}}
)
async def save_layout(body: LayoutBody):
    if len(body.layout) > MAX_LAYOUT_NODES or len(body.frames) > MAX_FRAMES:
        raise HTTPException(
            422,
            f"a board holds at most {MAX_LAYOUT_NODES} nodes and {MAX_FRAMES} frames",
        )
    canvas.save_layout(
        {node: {"x": at.x, "y": at.y} for node, at in body.layout.items()},
        [frame.model_dump() for frame in body.frames],
    )
    return {"ok": True}


@router.get("/sources")
async def studio_sources(session=Depends(get_session)):
    return await sources.estate(session)
