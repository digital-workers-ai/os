import uuid
from collections import Counter

from fastapi import Depends, HTTPException, Query
from sqlalchemy import func, select

from app.api.routers import entities as router
from app.caches import MAX_OFFSET
from app.db import async_session, get_session
from app.engine import run
from app.models import (
    CanonicalAlias,
    CanonicalLink,
    CanonicalMember,
    EngineRun,
    Entity,
    EntityCanonical,
    EntityFact,
    FactCurrent,
)

LABEL_ATTRS = ("name", "title", "subject", "email", "domain", "external_ref")


def _label(anchor: str, facts: dict) -> str:
    return next((facts[attr] for attr in LABEL_ATTRS if attr in facts), anchor)


@router.post("/rebuild")
async def rebuild():
    async with async_session() as session:
        try:
            return await run.rebuild(session)
        except run.RebuildInProgress as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records")
async def list_records(
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


@router.get("/entities")
async def list_entities(
    entity_type: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0, le=MAX_OFFSET),
    session=Depends(get_session),
):
    query = select(EntityCanonical).order_by(EntityCanonical.minted_seq)
    count_query = select(func.count()).select_from(EntityCanonical)
    if entity_type:
        query = query.where(EntityCanonical.entity_type == entity_type)
        count_query = count_query.where(EntityCanonical.entity_type == entity_type)
    total = (await session.execute(count_query)).scalar_one()
    rows = (await session.execute(query.limit(limit).offset(offset))).scalars().all()
    facts: dict = {}
    if rows:
        for fact in (
            (
                await session.execute(
                    select(FactCurrent).where(
                        FactCurrent.canonical_id.in_([r.canonical_id for r in rows])
                    )
                )
            )
            .scalars()
            .all()
        ):
            facts.setdefault(fact.canonical_id, {})[fact.attr] = fact.value
    by_type = dict(
        (
            await session.execute(
                select(EntityCanonical.entity_type, func.count()).group_by(
                    EntityCanonical.entity_type
                )
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
                "canonical_id": str(r.canonical_id),
                "entity_type": r.entity_type,
                "anchor": r.anchor_key,
                "label": _label(r.anchor_key, facts.get(r.canonical_id, {})),
                "members": r.member_count,
                "facts": facts.get(r.canonical_id, {}),
            }
            for r in rows
        ],
    }


@router.get(
    "/entities/{canonical_id}",
    responses={
        404: {
            "description": "no such canonical entity, or an "
            "alias pointing at a missing one"
        }
    },
)
async def get_entity(canonical_id: str, session=Depends(get_session)):
    try:
        wanted = uuid.UUID(str(canonical_id))
    except ValueError:
        raise HTTPException(404, "no such canonical entity") from None

    row = await session.get(EntityCanonical, wanted)
    resolved_from = None
    if row is None:
        alias = await session.get(CanonicalAlias, wanted)
        if alias is None:
            raise HTTPException(404, "no such canonical entity")
        if alias.reason == "retired":
            return {
                "canonical_id": str(wanted),
                "retired": True,
                "detail": "every member was deleted at its provider",
            }
        row = await session.get(EntityCanonical, alias.canonical_id)
        resolved_from = wanted
        if row is None:
            raise HTTPException(404, "alias points at a missing entity")

    facts = (
        await session.execute(
            select(FactCurrent, Entity.source)
            .join(Entity, Entity.id == FactCurrent.entity_id, isouter=True)
            .where(FactCurrent.canonical_id == row.canonical_id)
            .order_by(FactCurrent.attr)
        )
    ).all()
    members = (
        await session.execute(
            select(CanonicalMember, Entity)
            .join(Entity, Entity.id == CanonicalMember.entity_id)
            .where(CanonicalMember.canonical_id == row.canonical_id)
        )
    ).all()
    links_out = (
        (
            await session.execute(
                select(CanonicalLink).where(
                    CanonicalLink.from_canonical == row.canonical_id
                )
            )
        )
        .scalars()
        .all()
    )
    links_in = (
        (
            await session.execute(
                select(CanonicalLink).where(
                    CanonicalLink.to_canonical == row.canonical_id
                )
            )
        )
        .scalars()
        .all()
    )
    aliases = (
        (
            await session.execute(
                select(CanonicalAlias.alias_id).where(
                    CanonicalAlias.canonical_id == row.canonical_id
                )
            )
        )
        .scalars()
        .all()
    )

    return {
        "canonical_id": str(row.canonical_id),
        "entity_type": row.entity_type,
        "anchor": row.anchor_key,
        "label": _label(row.anchor_key, {f.attr: f.value for f, _ in facts}),
        "resolved_from_alias": str(resolved_from) if resolved_from else None,
        "aliases": [str(a) for a in aliases],
        "facts": [
            {
                "attr": f.attr,
                "value": f.value,
                "source": source,
                "raw_event_id": str(f.raw_event_id) if f.raw_event_id else None,
                "observed_at": f.observed_at.isoformat(),
                "disagreements": f.disagreements,
            }
            for f, source in facts
        ],
        "members": [
            {
                "source": e.source,
                "source_id": e.source_id,
                "object_type": e.object_type,
                "evidence": m.evidence,
            }
            for m, e in members
        ],
        "links": {
            "out": [
                {
                    "rel": link.rel,
                    "to": str(link.to_canonical),
                    "grounding": link.grounding,
                }
                for link in links_out
            ],
            "in": [
                {
                    "rel": link.rel,
                    "from": str(link.from_canonical),
                    "grounding": link.grounding,
                }
                for link in links_in
            ],
        },
    }


@router.get("/graph")
async def graph(
    entity_type: str | None = None,
    limit: int = Query(5000, ge=1, le=20000),
    session=Depends(get_session),
):
    wanted = (
        select(EntityCanonical.canonical_id)
        .order_by(EntityCanonical.minted_seq)
        .limit(limit)
    )
    if entity_type:
        wanted = wanted.where(EntityCanonical.entity_type == entity_type)
    nodes = (
        (
            await session.execute(
                select(EntityCanonical).where(EntityCanonical.canonical_id.in_(wanted))
            )
        )
        .scalars()
        .all()
    )
    edges = (
        (
            await session.execute(
                select(CanonicalLink).where(
                    CanonicalLink.from_canonical.in_(wanted),
                    CanonicalLink.to_canonical.in_(wanted),
                )
            )
        )
        .scalars()
        .all()
    )
    facts: dict = {}
    for canonical_id, attr, value in (
        await session.execute(
            select(FactCurrent.canonical_id, FactCurrent.attr, FactCurrent.value).where(
                FactCurrent.canonical_id.in_(wanted),
                FactCurrent.attr.in_(LABEL_ATTRS),
            )
        )
    ).all():
        facts.setdefault(canonical_id, {})[attr] = value
    by_type = Counter(n.entity_type for n in nodes)
    return {
        "nodes": [
            {
                "canonical_id": str(n.canonical_id),
                "entity_type": n.entity_type,
                "anchor": n.anchor_key,
                "label": _label(n.anchor_key, facts.get(n.canonical_id, {})),
                "members": n.member_count,
            }
            for n in sorted(nodes, key=lambda n: (n.entity_type, n.anchor_key))
        ],
        "edges": sorted(
            (
                {
                    "from": str(e.from_canonical),
                    "to": str(e.to_canonical),
                    "rel": e.rel,
                    "grounding": e.grounding,
                }
                for e in edges
            ),
            key=lambda e: (e["from"], e["to"], e["rel"]),
        ),
        "counts": {
            "nodes": len(nodes),
            "edges": len(edges),
            "by_type": dict(sorted(by_type.items())),
        },
    }


def _run_report(row: EngineRun) -> dict:
    return {
        "ran": True,
        "ok": row.ok,
        "duration_ms": row.duration_ms,
        "raw_events_read": row.raw_events_read,
        "entities": row.entities_written,
        "facts": row.facts_written,
        "candidates": row.report.get("totals", {}).get("candidates", 0),
        "created_at": row.created_at.isoformat(),
        "report": row.report,
    }


@router.get("/report")
async def latest_report(session=Depends(get_session)):
    newest = (
        await session.execute(select(EngineRun).order_by(EngineRun.seq.desc()).limit(1))
    ).scalar_one_or_none()
    if newest is None:
        return {"ran": False, "detail": "no rebuild has run yet"}
    return _run_report(newest)


@router.get("/report/runs")
async def list_runs(
    limit: int = Query(50, ge=1, le=200),
    session=Depends(get_session),
):
    rows = (
        (
            await session.execute(
                select(EngineRun).order_by(EngineRun.seq.desc()).limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return {
        "runs": [
            {
                "seq": r.seq,
                "ok": r.ok,
                "created_at": r.created_at.isoformat(),
                "duration_ms": r.duration_ms,
                "raw_events_read": r.raw_events_read,
                "entities": r.entities_written,
                "facts": r.facts_written,
                "totals": r.report.get("totals", {}),
                "error": r.report.get("error"),
            }
            for r in rows
        ]
    }


@router.get("/report/runs/{seq}", responses={404: {"description": "no such run"}})
async def get_run(seq: int, session=Depends(get_session)):
    row = (
        await session.execute(select(EngineRun).where(EngineRun.seq == seq))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "no such run")
    return _run_report(row)
