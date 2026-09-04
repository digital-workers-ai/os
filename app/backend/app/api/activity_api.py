from fastapi import Depends, Query
from sqlalchemy import select

from app.api.entities_api import LABEL_ATTRS, _label
from app.api.routers import activity as router
from app.db import get_session
from app.models import Entity, EntityCanonical, FactCurrent


@router.get("")
async def list_activity(
    limit: int = Query(200, ge=1, le=500),
    session=Depends(get_session),
):
    rows = (
        await session.execute(
            select(FactCurrent, EntityCanonical, Entity.source)
            .join(
                EntityCanonical,
                EntityCanonical.canonical_id == FactCurrent.canonical_id,
            )
            .join(Entity, Entity.id == FactCurrent.entity_id, isouter=True)
            .order_by(
                FactCurrent.observed_at.desc(),
                FactCurrent.canonical_id,
                FactCurrent.attr,
            )
            .limit(limit)
        )
    ).all()
    labels: dict = {}
    if rows:
        for canonical_id, attr, value in (
            await session.execute(
                select(
                    FactCurrent.canonical_id, FactCurrent.attr, FactCurrent.value
                ).where(
                    FactCurrent.canonical_id.in_([f.canonical_id for f, _, _ in rows]),
                    FactCurrent.attr.in_(LABEL_ATTRS),
                )
            )
        ).all():
            labels.setdefault(canonical_id, {})[attr] = value
    return {
        "events": [
            {
                "observed_at": fact.observed_at.isoformat(),
                "canonical_id": str(fact.canonical_id),
                "entity_type": entity.entity_type,
                "label": _label(entity.anchor_key, labels.get(fact.canonical_id, {})),
                "source": source,
                "attr": fact.attr,
                "value": fact.value,
            }
            for fact, entity, source in rows
        ]
    }
