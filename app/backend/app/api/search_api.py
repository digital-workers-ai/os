from fastapi import Depends, HTTPException, Query

from app import llm
from app.api.routers import search as router
from app.caches import MAX_OFFSET
from app.db import async_session, get_session
from app.engine import search


@router.get("")
async def query(
    q: str = Query(..., min_length=1, max_length=200),
    kind: str | None = None,
    mode: str = Query("words", pattern="^(words|meaning|both)$"),
    limit: int = Query(10, ge=1, le=500),
    offset: int = Query(0, ge=0, le=MAX_OFFSET),
    session=Depends(get_session),
):
    try:
        return await search.query(
            session, q, kind=kind, mode=mode, limit=limit, offset=offset
        )
    except search.SearchError as exc:
        status = 422 if str(exc).startswith("unknown kind") else 409
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    except llm.LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/embed")
async def embed(limit: int | None = Query(None, ge=1, le=1000)):
    async with async_session() as session:
        try:
            return await search.embed(session, limit=limit)
        except search.SearchError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
