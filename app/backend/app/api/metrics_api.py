from fastapi import Depends, Query
from sqlalchemy import select

from app import clock
from app.api.routers import metrics as router
from app.db import async_session, get_session
from app.engine import mappings, metrics
from app.models import MetricSnapshot

GLOSS_KEYS = ("description", "synonyms")


@router.get("")
async def get_metrics(session=Depends(get_session)):
    now = clock.now()
    values = await metrics.evaluate(session, now=now)
    defs = metrics.load_definitions()
    lineage = metrics.provenance(defs, mappings.load())
    for name, row in values.items():
        spec = defs[name]
        row.update(lineage.get(name, {}))
        row.update({key: spec[key] for key in GLOSS_KEYS if key in spec})
    return {"as_of": now.isoformat(), "metrics": values}


@router.post("/snapshots")
async def write_snapshots():
    async with async_session() as session:
        written = await metrics.record_snapshots(session)
        await session.commit()
    return {"written": written}


@router.get("/history")
async def get_history(
    metric: str | None = None,
    limit: int = Query(200, ge=1, le=2000),
    session=Depends(get_session),
):
    query = (
        select(MetricSnapshot).order_by(MetricSnapshot.recorded_at.desc()).limit(limit)
    )
    if metric:
        query = query.where(MetricSnapshot.metric == metric)
    rows = (await session.execute(query)).scalars().all()
    return {
        "history": [
            {
                "metric": row.metric,
                "value": row.value,
                "entities": row.entities,
                "inferred": row.inferred,
                "produced_by": row.produced_by,
                "vocabulary_sha": (row.vocabulary_sha or "")[:12] or None,
                "recorded_at": row.recorded_at.isoformat(),
            }
            for row in rows
        ]
    }


@router.get("/history/{metric}")
async def get_series(
    metric: str,
    limit: int = Query(500, ge=1, le=2000),
    session=Depends(get_session),
):
    return await metrics.history(session, metric, limit=limit)
