from fastapi import Depends, Query

from app import competition
from app.api.routers import competitors as router
from app.db import get_session


@router.get("/competitors/ads")
async def competitor_ads(
    platform: str = Query(..., pattern="^(meta|google)$"),
    session=Depends(get_session),
):
    return await competition.ads(session, platform)


@router.get("/competitors/rankings")
async def competitor_rankings(session=Depends(get_session)):
    return await competition.rankings(session)


@router.get("/competitors/answers")
async def competitor_answers(session=Depends(get_session)):
    return await competition.answers(session)


@router.get("/competitors/pages")
async def competitor_pages(session=Depends(get_session)):
    return await competition.pages(session)


@router.get("/competitors/posts")
async def competitor_posts(session=Depends(get_session)):
    return await competition.posts(session)
