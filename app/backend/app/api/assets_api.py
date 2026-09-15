from fastapi import BackgroundTasks, Depends, HTTPException, Query, Response
from pydantic import BaseModel

from app.api.routers import assets as router
from app.caches import MAX_OFFSET
from app.db import get_session
from app.skills import runner
from app.studio import assets, errors


class RebuildBody(BaseModel):
    note: str


class FeedbackBody(BaseModel):
    text: str


@router.get("/assets")
async def list_assets(
    kind: str | None = None,
    look: str | None = None,
    origin: str | None = None,
    q: str | None = None,
    skill: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0, le=MAX_OFFSET),
    session=Depends(get_session),
):
    return await assets.listing(session, kind, look, origin, q, skill, limit, offset)


@router.get("/assets/{seq}", responses={404: {"description": "no such asset"}})
async def read_asset(seq: int, session=Depends(get_session)):
    try:
        return await assets.detail(session, seq)
    except errors.Missing as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get(
    "/assets/{seq}/files/{path:path}",
    responses={404: {"description": "no such file"}, 409: {"description": "refused"}},
)
async def read_asset_file(seq: int, path: str, session=Depends(get_session)):
    try:
        data, media_type = await assets.file_bytes(session, seq, path)
    except errors.Missing as exc:
        raise HTTPException(404, str(exc)) from exc
    except errors.Refused as exc:
        raise HTTPException(409, str(exc)) from exc
    return Response(content=data, media_type=media_type)


@router.post(
    "/assets/{seq}/rebuild",
    responses={404: {"description": "no such asset"}, 409: {"description": "refused"}},
)
async def rebuild_asset(
    seq: int,
    background: BackgroundTasks,
    body: RebuildBody,
    session=Depends(get_session),
):
    try:
        started = await assets.rebuild(session, seq, body.note)
    except errors.Missing as exc:
        raise HTTPException(404, str(exc)) from exc
    except errors.Refused as exc:
        raise HTTPException(409, str(exc)) from exc
    await session.commit()
    background.add_task(runner.execute_detached, started.skill_run, started.ask)
    return {"skill_run": started.skill_run}


@router.post(
    "/assets/{seq}/feedback", responses={404: {"description": "no such asset"}}
)
async def send_feedback(seq: int, body: FeedbackBody, session=Depends(get_session)):
    try:
        found = await assets.feedback(session, seq, body.text)
    except errors.Missing as exc:
        raise HTTPException(404, str(exc)) from exc
    await session.commit()
    return found
