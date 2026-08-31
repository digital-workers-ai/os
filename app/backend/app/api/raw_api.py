from fastapi import Depends, Query
from sqlalchemy import func, select

from app.api.routers import raw as router
from app.db import get_session
from app.models import RawEvent

MAX_OFFSET = 2**63 - 1


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
        "events": [
            {
                "id": str(r.id),
                "seq": r.seq,
                "source": r.source,
                "object_type": r.object_type,
                "source_id": r.source_id,
                "ingested_at": r.ingested_at.isoformat(),
                "raw_payload": r.raw_payload,
            }
            for r in rows
        ],
    }
