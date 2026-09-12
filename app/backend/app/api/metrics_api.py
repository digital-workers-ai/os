from datetime import date
from typing import Literal

from fastapi import Depends, HTTPException, Query
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


@router.get("/{name}", responses={404: {"description": "no such metric"}})
async def get_metric(
    name: str,
    from_: date | None = Query(None, alias="from"),
    to: date | None = Query(None),
    compare: Literal["previous"] | None = Query(None),
    session=Depends(get_session),
):
    defs = metrics.load_definitions()
    if name not in defs:
        raise HTTPException(404, "no such metric")
    if (from_ is None) != (to is None):
        raise HTTPException(422, "from and to travel together")
    bounds = None
    if from_ is not None:
        if from_ > to:
            raise HTTPException(422, "from must not be after to")
        bounds = (from_.isoformat(), to.isoformat())
    if compare and bounds is None:
        raise HTTPException(422, "compare needs from and to")
    spec = defs[name]
    now = clock.now()
    try:
        row = await metrics.evaluate_one(
            session, name, spec, now=now, bounds=bounds, compare=compare
        )
    except metrics.MetricSpecError as e:
        raise HTTPException(422, str(e)) from e
    lineage = metrics.provenance(defs, mappings.load())
    return {
        "as_of": now.isoformat(),
        "metric": name,
        **row,
        **lineage.get(name, {}),
        **{key: spec[key] for key in GLOSS_KEYS if key in spec},
    }
