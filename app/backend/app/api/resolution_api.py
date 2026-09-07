from datetime import UTC, datetime
from typing import Literal

from fastapi import Depends, HTTPException, Query
from sqlalchemy import func, select, tuple_

from app.api.entities_api import LABEL_ATTRS, _label
from app.api.routers import resolution as router
from app.db import async_session, get_session
from app.engine import run
from app.models import (
    CanonicalMember,
    Entity,
    EntityFact,
    MergeCandidate,
    MergeCandidateEvidence,
)

STATUSES = ("pending", "confirmed", "rejected")
DECISIONS = {
    "confirm": ("confirmed", ("pending", "rejected")),
    "reject": ("rejected", ("pending", "confirmed")),
    "unmerge": ("pending", ("confirmed",)),
}
NOT_FOUND = {404: {"description": "no such candidate"}}


@router.get("/candidates")
async def list_candidates(
    status: Literal["pending", "confirmed", "rejected", "all"] = "pending",
    limit: int = Query(200, ge=1, le=500),
    session=Depends(get_session),
):
    query = select(MergeCandidate).order_by(MergeCandidate.seq.desc()).limit(limit)
    if status != "all":
        query = query.where(MergeCandidate.status == status)
    rows = (await session.execute(query)).scalars().all()
    counted = dict(
        (
            await session.execute(
                select(MergeCandidate.status, func.count()).group_by(
                    MergeCandidate.status
                )
            )
        ).all()
    )
    return {
        "candidates": await _items(session, rows),
        "counts": {name: counted.get(name, 0) for name in STATUSES},
    }


@router.post("/candidates/{seq}/confirm", responses=NOT_FOUND)
async def confirm(seq: int):
    return await _decide(seq, "confirm")


@router.post("/candidates/{seq}/reject", responses=NOT_FOUND)
async def reject(seq: int):
    return await _decide(seq, "reject")


@router.post("/candidates/{seq}/unmerge", responses=NOT_FOUND)
async def unmerge(seq: int):
    return await _decide(seq, "unmerge")


async def _decide(seq: int, decision: str) -> dict:
    status, allowed = DECISIONS[decision]
    async with async_session() as session:
        row = await session.get(MergeCandidate, seq)
        if row is None:
            raise HTTPException(404, "no such candidate")
        if row.status not in allowed:
            raise HTTPException(
                409,
                f"candidate {seq} is {row.status}; {decision} applies to a "
                f"{' or '.join(allowed)} pair",
            )
        row.status = status
        row.decided_at = None if status == "pending" else datetime.now(UTC)
        await session.flush()
        try:
            await run.rebuild(session)
        except run.RebuildInProgress as exc:
            raise HTTPException(409, str(exc)) from exc
        current = (
            await session.execute(
                select(MergeCandidate)
                .where(
                    MergeCandidate.entity_type == row.entity_type,
                    MergeCandidate.left_anchor == row.left_anchor,
                    MergeCandidate.right_anchor == row.right_anchor,
                )
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        [item] = await _items(session, [current or row])
        return item


async def _items(session, rows) -> list:
    if not rows:
        return []
    anchors = sorted(
        {anchor for row in rows for anchor in (row.left_anchor, row.right_anchor)}
    )
    entities = (
        (
            await session.execute(
                select(Entity).where(
                    tuple_(Entity.source, Entity.entity_type, Entity.source_id).in_(
                        [tuple(anchor.split("|", 2)) for anchor in anchors]
                    )
                )
            )
        )
        .scalars()
        .all()
    )
    by_anchor = {f"{e.source}|{e.entity_type}|{e.source_id}": e for e in entities}
    ids = [e.id for e in entities]
    clusters = dict(
        (
            await session.execute(
                select(CanonicalMember.entity_id, CanonicalMember.canonical_id).where(
                    CanonicalMember.entity_id.in_(ids)
                )
            )
        ).all()
    )
    facts: dict = {}
    for entity_id, attr, value in (
        await session.execute(
            select(EntityFact.entity_id, EntityFact.attr, EntityFact.value).where(
                EntityFact.entity_id.in_(ids),
                EntityFact.attr.in_(LABEL_ATTRS),
                EntityFact.is_null.is_(False),
            )
        )
    ).all():
        facts.setdefault(entity_id, {})[attr] = value
    evidence: dict = {}
    for found in (
        (
            await session.execute(
                select(MergeCandidateEvidence)
                .where(
                    MergeCandidateEvidence.candidate_seq.in_([row.seq for row in rows])
                )
                .order_by(MergeCandidateEvidence.seq)
            )
        )
        .scalars()
        .all()
    ):
        evidence.setdefault(found.candidate_seq, []).append(
            {
                "attr": found.attr,
                "left_value": found.left_value,
                "right_value": found.right_value,
            }
        )

    def side(anchor: str) -> dict:
        entity = by_anchor.get(anchor)
        cluster = clusters.get(entity.id) if entity else None
        return {
            "anchor": anchor,
            "canonical_id": str(cluster) if cluster else None,
            "label": _label(anchor, facts.get(entity.id, {}) if entity else {}),
        }

    return [
        {
            "seq": row.seq,
            "entity_type": row.entity_type,
            "left": side(row.left_anchor),
            "right": side(row.right_anchor),
            "score": row.score,
            "status": row.status,
            "evidence_holds": row.evidence_holds,
            "decided_at": row.decided_at.isoformat() if row.decided_at else None,
            "evidence": evidence.get(row.seq, []),
        }
        for row in rows
    ]
