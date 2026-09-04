from fastapi import Body, Depends, HTTPException, Query
from pydantic import BaseModel, StrictBool
from sqlalchemy import func, select

from app import sync
from app.api.routers import sources as router
from app.caches import MAX_OFFSET
from app.db import async_session, get_session
from app.engine import checks
from app.models import SyncRun
from app.sources import catalog, registry


@router.get("/sources")
async def list_sources(session=Depends(get_session)):
    status_rows = {r["source"]: r for r in await sync.status(session)}
    disabled = await sync.disabled_sources(session)
    validation = checks.source_status()
    rows = []
    for entry in catalog.catalog():
        source = entry["source"]
        derived = validation[source]
        rows.append(
            {
                **entry,
                **status_rows.get(source, {}),
                "validation": derived["status"],
                "entities": derived["entities"],
                "enabled": source not in disabled,
            }
        )
    return {"sources": rows, "validation_coverage": _coverage(rows)}


class EnabledBody(BaseModel):
    enabled: StrictBool


@router.put(
    "/sources/{source}/enabled",
    responses={404: {"description": "no such source"}},
)
async def set_source_enabled(
    source: str, body: EnabledBody, session=Depends(get_session)
):
    if source not in registry.discover():
        raise HTTPException(404, "no such source")
    result = await sync.set_enabled(session, source, body.enabled)
    await session.commit()
    return result


def _coverage(rows: list) -> dict:
    counts: dict = {}
    for row in rows:
        counts[row["validation"]] = counts.get(row["validation"], 0) + 1
    provider = counts.get("provider-validated", 0)
    return {
        "provider_validated": provider,
        "total": len(rows),
        "by_status": dict(sorted(counts.items())),
        "detail": (
            f"{provider} of {len(rows)} sources have replayed a real "
            "provider payload"
            + (
                ""
                if provider
                else " — every number below is mock-validated only, which "
                "proves the knowledge files agree with our own mocks, "
                "not with any provider"
            )
        ),
    }


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
    try:
        return await sync.run_all(async_session, sources)
    except sync.SourceDisabled as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/sync/runs")
async def list_sync_runs(
    source: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0, le=MAX_OFFSET),
    session=Depends(get_session),
):
    query = select(SyncRun).order_by(SyncRun.started_at.desc(), SyncRun.id)
    count_query = select(func.count()).select_from(SyncRun)
    if source:
        query = query.where(SyncRun.source == source)
        count_query = count_query.where(SyncRun.source == source)
    total = (await session.execute(count_query)).scalar_one()
    rows = (await session.execute(query.limit(limit).offset(offset))).scalars().all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "runs": [
            {
                "id": str(r.id),
                "source": r.source,
                "ok": r.ok,
                "rows_written": r.rows_written,
                "detail": r.detail,
                "started_at": r.started_at.isoformat(),
            }
            for r in rows
        ],
    }
