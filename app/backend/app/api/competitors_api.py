from fastapi import BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.routers import competitors as router
from app.caches import MAX_OFFSET
from app.db import get_session
from app.skills import runner
from app.studio import errors, swipe


class RemixBody(BaseModel):
    kind: str
    look: str | None = None
    slot: str | None = None
    keep: list[str] = []


@router.get("/competitors")
async def list_competitors(session=Depends(get_session)):
    return await swipe.companies(session)


@router.get("/competitors/swipe")
async def swipe_file(
    competitor: str | None = None,
    platform: str | None = None,
    angle: str | None = None,
    hook: str | None = None,
    fmt: str | None = Query(None, alias="format"),
    sort: str = "days_running",
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0, le=MAX_OFFSET),
    session=Depends(get_session),
):
    return await swipe.file(
        session, competitor, platform, angle, hook, fmt, sort, limit, offset
    )


@router.get(
    "/competitors/swipe/{item_id}", responses={404: {"description": "no such item"}}
)
async def swipe_item(item_id: str, session=Depends(get_session)):
    try:
        return await swipe.item(session, item_id)
    except errors.Missing as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post(
    "/competitors/swipe/{item_id}/remix",
    responses={404: {"description": "no such item"}, 409: {"description": "refused"}},
)
async def remix_item(
    item_id: str,
    background: BackgroundTasks,
    body: RemixBody,
    session=Depends(get_session),
):
    try:
        seq, started = await swipe.remix(
            session, item_id, body.kind, body.look, body.slot, body.keep
        )
    except errors.Missing as exc:
        raise HTTPException(404, str(exc)) from exc
    except errors.Refused as exc:
        raise HTTPException(409, str(exc)) from exc
    await session.commit()
    background.add_task(runner.execute_detached, started.skill_run, started.ask)
    return {"proposal": seq}


@router.get("/competitors/ads")
async def competitor_ads(
    competitor: str | None = None,
    platform: str | None = None,
    session=Depends(get_session),
):
    return await swipe.ads(session, competitor, platform)


@router.get("/competitors/rankings")
async def competitor_rankings(keyword: str | None = None, session=Depends(get_session)):
    return await swipe.rankings(session, keyword)


@router.get("/competitors/answers")
async def competitor_answers(prompt: str | None = None, session=Depends(get_session)):
    return await swipe.answers(session, prompt)


@router.get("/competitors/content")
async def competitor_content(session=Depends(get_session)):
    return await swipe.content(session)
