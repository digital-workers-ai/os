import uuid

from fastapi import Depends, HTTPException, Query
from sqlalchemy import func, select

from app.api.routers import raw as router
from app.caches import MAX_OFFSET
from app.db import get_session
from app.models import RawEvent


def _event(row: RawEvent) -> dict:
    return {
        "id": str(row.id),
        "seq": row.seq,
        "source": row.source,
        "object_type": row.object_type,
        "source_id": row.source_id,
        "ingested_at": row.ingested_at.isoformat(),
        "raw_payload": row.raw_payload,
    }


@router.get("")
async def list_raw(
    source: str | None = None,
    object_type: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0, le=MAX_OFFSET),
    session=Depends(get_session),
):
    query = select(RawEvent).order_by(RawEvent.seq.desc())
    count_query = select(func.count()).select_from(RawEvent)
    if source:
        query = query.where(RawEvent.source == source)
        count_query = count_query.where(RawEvent.source == source)
    if object_type:
        query = query.where(RawEvent.object_type == object_type)
        count_query = count_query.where(RawEvent.object_type == object_type)
    total = (await session.execute(count_query)).scalar_one()
    rows = (await session.execute(query.limit(limit).offset(offset))).scalars().all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "events": [_event(r) for r in rows],
    }


@router.get("/{event_id}", responses={404: {"description": "no such event"}})
async def get_raw(event_id: str, session=Depends(get_session)):
    try:
        wanted = uuid.UUID(event_id)
    except ValueError:
        raise HTTPException(404, "no such event") from None
    row = await session.get(RawEvent, wanted)
    if row is None:
        raise HTTPException(404, "no such event")
    return _event(row)
