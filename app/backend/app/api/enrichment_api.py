import uuid

from fastapi import Depends, HTTPException, Query
from sqlalchemy import func, select

from app.api.entities_api import LABEL_ATTRS, _label
from app.api.routers import enrichment as router
from app.caches import MAX_OFFSET
from app.config import settings
from app.db import async_session, get_session
from app.enrichment import store as enrichment_store
from app.enrichment import vocabulary as vocab_mod
from app.models import EnrichedFact, EntityCanonical, FactCurrent


@router.get("/vocabulary")
async def vocabulary():
    readings = vocab_mod.load()
    return {
        "enabled": settings.ENRICHMENT_ENABLED,
        "model": settings.ENRICHMENT_MODEL,
        "readings": {
            name: {
                "entity": r.entity,
                "input": r.input_attr,
                "description": r.description,
                "sha": r.sha,
                "fields": [
                    {
                        "name": f.name,
                        "type": f.kind,
                        "description": f.description,
                        "labels": [
                            {"label": label, "means": meaning}
                            for label, meaning in f.glosses
                        ],
                    }
                    for f in r.fields
                ],
            }
            for name, r in sorted(readings.items())
        },
    }


@router.post("/run")
async def run(
    reading: str | None = None,
    force: bool = False,
    limit: int | None = Query(None, ge=1, le=1000),
):
    async with async_session() as session:
        try:
            return await enrichment_store.enrich(
                session, reading_name=reading, force=force, limit=limit
            )
        except enrichment_store.EnrichmentError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("")
async def list_enriched(
    attr: str | None = None,
    value: str | None = None,
    entity_type: str | None = None,
    unverified_only: bool = False,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0, le=MAX_OFFSET),
    session=Depends(get_session),
):
    narrowing = (
        ([EnrichedFact.attr == attr] if attr else [])
        + ([EnrichedFact.value == value] if value else [])
        + ([EnrichedFact.entity_type == entity_type] if entity_type else [])
    )
    unverified_clause = EnrichedFact.quote_verified.is_(False)
    page = [*narrowing, unverified_clause] if unverified_only else narrowing
    query = select(EnrichedFact).where(*page)
    count = select(func.count()).select_from(EnrichedFact).where(*page)

    total = (await session.execute(count)).scalar_one()
    rows = (
        (
            await session.execute(
                query.order_by(
                    EnrichedFact.created_at.desc(),
                    EnrichedFact.attr,
                    EnrichedFact.value,
                )
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )

    anchors: dict = {}
    labels: dict = {}
    if rows:
        ids = {r.canonical_id for r in rows}
        anchors = dict(
            (
                await session.execute(
                    select(
                        EntityCanonical.canonical_id,
                        EntityCanonical.anchor_key,
                    ).where(EntityCanonical.canonical_id.in_(ids))
                )
            ).all()
        )
        for canonical_id, label_attr, label_value in (
            await session.execute(
                select(
                    FactCurrent.canonical_id,
                    FactCurrent.attr,
                    FactCurrent.value,
                ).where(
                    FactCurrent.canonical_id.in_(ids),
                    FactCurrent.attr.in_(LABEL_ATTRS),
                )
            )
        ).all():
            labels.setdefault(canonical_id, {})[label_attr] = label_value

    readings = vocab_mod.load()
    current = {r.sha for r in readings.values()}
    by_value = {
        f"{rd}.{attr_name}.{label}": n
        for rd, attr_name, label, n in (
            await session.execute(
                select(
                    EnrichedFact.reading,
                    EnrichedFact.attr,
                    EnrichedFact.value,
                    func.count(),
                )
                .where(EnrichedFact.vocabulary_sha.in_(current))
                .group_by(EnrichedFact.reading, EnrichedFact.attr, EnrichedFact.value)
            )
        ).all()
    }
    unverified = (
        await session.execute(
            select(func.count())
            .select_from(EnrichedFact)
            .where(*narrowing, unverified_clause)
        )
    ).scalar_one()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "unverified_quotes": unverified,
        "by_value": dict(sorted(by_value.items())),
        "coverage": [
            await enrichment_store.coverage(session, r)
            for _name, r in sorted(readings.items())
        ],
        "inferred": True,
        "counts": "model readings under the current vocabulary, not measurements",
        "facts": [
            {
                "canonical_id": str(r.canonical_id),
                "entity_type": r.entity_type,
                "label": _label(
                    anchors.get(r.canonical_id, str(r.canonical_id)),
                    labels.get(r.canonical_id, {}),
                ),
                "reading": r.reading,
                "attr": r.attr,
                "value": r.value,
                "quote": r.quote,
                "quote_verified": r.quote_verified,
                "model": r.model,
                "prompt_version": r.prompt_version,
                "vocabulary_sha": r.vocabulary_sha[:12],
            }
            for r in rows
        ],
    }


@router.get("/coverage")
async def coverage(session=Depends(get_session)):
    return {
        "readings": [
            await enrichment_store.coverage(session, r)
            for _name, r in sorted(vocab_mod.load().items())
        ]
    }


@router.get("/{canonical_id}", responses={404: {"description": "not a canonical id"}})
async def for_entity(canonical_id: str, session=Depends(get_session)):
    try:
        parsed = uuid.UUID(canonical_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="no such entity") from None
    return {
        "canonical_id": canonical_id,
        "inferred": True,
        "facts": await enrichment_store.for_entity(session, parsed),
    }
