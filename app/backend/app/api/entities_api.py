from fastapi import Depends, HTTPException, Query
from sqlalchemy import func, select

from app.api.routers import entities as router
from app.caches import MAX_OFFSET
from app.db import async_session, get_session
from app.engine import run
from app.models import EngineRun, Entity, EntityFact


@router.post("/rebuild")
async def rebuild():
    async with async_session() as session:
        try:
            return await run.rebuild(session)
        except run.RebuildInProgress as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/entities")
async def list_entities(
    entity_type: str | None = None,
    source: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0, le=MAX_OFFSET),
    session=Depends(get_session),
):
    query = select(Entity).order_by(Entity.first_seq)
    count_query = select(func.count()).select_from(Entity)
    if entity_type:
        query = query.where(Entity.entity_type == entity_type)
        count_query = count_query.where(Entity.entity_type == entity_type)
    if source:
        query = query.where(Entity.source == source)
        count_query = count_query.where(Entity.source == source)
    total = (await session.execute(count_query)).scalar_one()
    rows = (await session.execute(query.limit(limit).offset(offset))).scalars().all()
    facts: dict = {}
    if rows:
        for fact in (
            (
                await session.execute(
                    select(EntityFact).where(
                        EntityFact.entity_id.in_([r.id for r in rows])
                    )
                )
            )
            .scalars()
            .all()
        ):
            facts.setdefault(fact.entity_id, {})[fact.attr] = (
                None if fact.is_null else fact.value
            )
    by_type = dict(
        (
            await session.execute(
                select(Entity.entity_type, func.count()).group_by(Entity.entity_type)
            )
        ).all()
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "by_type": dict(sorted(by_type.items())),
        "entities": [
            {
                "source": r.source,
                "entity_type": r.entity_type,
                "source_id": r.source_id,
                "object_type": r.object_type,
                "facts": facts.get(r.id, {}),
            }
            for r in rows
        ],
    }


@router.get("/report")
async def latest_report(session=Depends(get_session)):
    newest = (
        await session.execute(select(EngineRun).order_by(EngineRun.seq.desc()).limit(1))
    ).scalar_one_or_none()
    if newest is None:
        return {"ran": False, "detail": "no rebuild has run yet"}
    return {
        "ran": True,
        "ok": newest.ok,
        "duration_ms": newest.duration_ms,
        "raw_events_read": newest.raw_events_read,
        "entities": newest.entities_written,
        "facts": newest.facts_written,
        "created_at": newest.created_at.isoformat(),
        "report": newest.report,
    }
