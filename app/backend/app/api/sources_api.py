from fastapi import Body, HTTPException

from app import sync
from app.api.routers import sources as router
from app.db import async_session
from app.sources import registry


@router.post("/sync")
async def run_sync(body: dict = Body(default={})):
    sources = body.get("sources")
    if sources is None:
        return await sync.run_all(async_session)
    if not isinstance(sources, list):
        raise HTTPException(422, "`sources` must be a list of source names")
    if not sources:
        return {"ok": 0, "failed": 0, "rows_written": 0, "results": []}
    unknown = sorted(set(sources) - set(registry.discover()))
    if unknown:
        raise HTTPException(404, f"unknown source(s): {unknown}")
    return await sync.run_all(async_session, sources)
