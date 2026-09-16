from typing import Annotated

from fastapi import BackgroundTasks, Depends, HTTPException, Query, Response
from pydantic import BaseModel, StringConstraints

from app.api.routers import assets as router
from app.caches import MAX_OFFSET
from app.db import get_session
from app.models import SkillRun
from app.skills import runner
from app.studio import Missing, assets, rows

NOT_FOUND = {404: {"description": "no such asset or file"}}
CANNOT_RUN = {409: {"description": "the run cannot open"}}
CLIMBS = {409: {"description": "the path climbs out of its version"}}


class TextBody(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class RatioBody(BaseModel):
    ratio: str


async def _opened(session, background, opening) -> dict:
    try:
        started, ask = await opening
    except Missing as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (assets.Refused, runner.SkillError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    run = await session.get(SkillRun, started.skill_run)
    await session.commit()
    background.add_task(runner.execute_detached, started.skill_run, ask)
    return {"skill_run": rows.skill_run_row(run), "version": started.version}


@router.get("/assets")
async def list_assets(
    kind: str | None = None,
    look: str | None = None,
    origin: str | None = None,
    q: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0, le=MAX_OFFSET),
    session=Depends(get_session),
):
    return await assets.listing(
        session, kind=kind, look=look, origin=origin, q=q, limit=limit, offset=offset
    )


@router.get("/assets/{seq}", responses=NOT_FOUND)
async def get_asset(seq: int, session=Depends(get_session)):
    try:
        return await assets.detail(session, seq)
    except Missing as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/assets/{seq}/versions/{version}/files/{path:path}",
    responses={**NOT_FOUND, **CLIMBS},
)
async def get_asset_file(
    seq: int, version: int, path: str, session=Depends(get_session)
):
    try:
        data, media_type = await assets.file_bytes(session, seq, version, path)
    except Missing as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except assets.Refused as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(content=data, media_type=media_type)


@router.post("/assets/{seq}/edit", responses={**NOT_FOUND, **CANNOT_RUN})
async def edit_asset(
    seq: int, body: TextBody, background: BackgroundTasks, session=Depends(get_session)
):
    return await _opened(session, background, assets.edit(session, seq, body.text))


@router.post("/assets/{seq}/resize", responses={**NOT_FOUND, **CANNOT_RUN})
async def resize_asset(
    seq: int,
    body: RatioBody,
    background: BackgroundTasks,
    session=Depends(get_session),
):
    return await _opened(session, background, assets.resize(session, seq, body.ratio))


@router.post("/assets/{seq}/feedback", responses=NOT_FOUND)
async def feedback_asset(seq: int, body: TextBody, session=Depends(get_session)):
    try:
        detail = await assets.feedback(session, seq, body.text)
    except Missing as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return detail
