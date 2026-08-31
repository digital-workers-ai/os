import time
import uuid

from sqlalchemy import delete, func, select

from app.config import settings
from app.engine import (
    links,
    mappings,
    ontology,
    pipeline,
    resolver,
    survivorship,
    transforms,
)
from app.engine.report import SyncReport
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
from app.sources import registry
from app.store import first_seen_query, latest_rows_query

NAMESPACE = resolver.NAMESPACE

_REBUILD_LOCK_ID = 0x_5EB1D


class RebuildInProgress(RuntimeError):
    pass


def _uuid(*parts) -> uuid.UUID:
    return uuid.uuid5(resolver.NAMESPACE, "|".join(str(p) for p in parts))


def _resolver_records(projected: dict, onto) -> list:
    records = []
    for entity in projected.values():
        identity = {}
        for attr in onto.identity_attrs(entity.entity_type):
            fact = entity.facts.get(attr)
            if fact is not None and fact.value is not None:
                identity[attr] = fact.value
        records.append(
            resolver.Record(
                source=entity.source,
                entity_type=entity.entity_type,
                source_id=entity.source_id,
                order=entity.first_seq,
                identity=identity,
            )
        )
    return records


async def _clear_projection(session) -> None:
    for table in (
        CanonicalLink,
        FactCurrent,
        CanonicalMember,
        CanonicalAlias,
        EntityCanonical,
        EntityFact,
        Entity,
    ):
        await session.execute(delete(table))


async def rebuild(session) -> dict:
    started = time.monotonic()
    report = SyncReport()

    got_lock = (
        await session.execute(select(func.pg_try_advisory_xact_lock(_REBUILD_LOCK_ID)))
    ).scalar_one()
    if not got_lock:
        raise RebuildInProgress(
            "a rebuild is already in progress; it recomputes the whole "
            "projection, so a second one has nothing to add"
        )

    onto = ontology.load()
    lines = mappings.load()
    line_index = mappings.by_object(lines)
    transform_map = transforms.load_map()
    connectors = registry.discover()
    for line in lines:
        report.declare_path(line.entity, line.key)

    rows = (await session.execute(latest_rows_query())).scalars().all()
    rows = sorted(rows, key=lambda r: r.seq)
    report.count("raw_events_read", len(rows))

    first_seen = {
        (source, object_type, source_id): seq
        for source, object_type, source_id, seq, _ingested_at in (
            await session.execute(first_seen_query())
        ).all()
    }

    projected = pipeline.project_rows(
        rows,
        onto=onto,
        line_index=line_index,
        transform_map=transform_map,
        report=report,
        connectors=connectors,
        first_seen=first_seen,
    )

    resolution = resolver.resolve(_resolver_records(projected, onto), onto, report)
    folded = survivorship.fold(resolution["clusters"], projected, onto, report)

    previously = dict(
        (
            await session.execute(
                select(EntityCanonical.canonical_id, EntityCanonical.anchor_key)
            )
        ).all()
    )

    live_canonical = {f.canonical_id for f in folded}
    edges = links.build(
        onto, projected=projected, of_record=resolution["of_record"], report=report
    )
    edges = [
        e
        for e in edges
        if e.from_canonical in live_canonical and e.to_canonical in live_canonical
    ]

    aliases: dict = {}
    retired: list = []
    of_record = resolution["of_record"]
    for old_id, anchor_key in sorted(previously.items(), key=lambda p: str(p[0])):
        if old_id in live_canonical or old_id in aliases or old_id in retired:
            continue
        parts = anchor_key.split("|", 2)
        target = of_record.get(tuple(parts))
        if target is not None and target in live_canonical:
            aliases[old_id] = target
        else:
            retired.append(old_id)

    await _write(
        session,
        projected=projected,
        clusters=resolution["clusters"],
        aliases=aliases,
        retired=retired,
        folded=folded,
        edges=edges,
    )

    live_clusters = [
        c for c in resolution["clusters"] if c.canonical_id in live_canonical
    ]
    for cluster in live_clusters:
        report.count(f"canonical/{cluster.entity_type}")
    for entity in projected.values():
        report.count(f"records/{entity.source}/{entity.entity_type}")

    facts_written = sum(len(e.facts) for e in projected.values())
    duration_ms = int((time.monotonic() - started) * 1000)
    run = EngineRun(
        ok=True,
        raw_events_read=len(rows),
        entities_written=len(projected),
        facts_written=facts_written,
        canonical_written=len(live_clusters),
        links_written=len(edges),
        report=report.as_dict(),
        duration_ms=duration_ms,
    )
    session.add(run)
    await session.flush()
    await prune(session)
    await session.commit()
    return {
        "ok": True,
        "duration_ms": duration_ms,
        "raw_events_read": len(rows),
        "entities": len(projected),
        "canonical": len(live_clusters),
        "facts": len(folded),
        "links": len(edges),
        "report": report.as_dict(),
    }


async def _write(session, *, projected, clusters, aliases, retired, folded, edges):
    await _clear_projection(session)

    entity_ids: dict = {}
    entity_rows, fact_rows = [], []
    for key, entity in sorted(projected.items()):
        entity_id = _uuid("entity", entity.anchor_key)
        entity_ids[key] = entity_id
        entity_rows.append(
            {
                "id": entity_id,
                "source": entity.source,
                "entity_type": entity.entity_type,
                "source_id": entity.source_id,
                "object_type": entity.object_type,
                "first_seq": entity.first_seq,
            }
        )
        for attr, fact in sorted(entity.facts.items()):
            fact_rows.append(
                {
                    "id": _uuid("fact", entity.anchor_key, attr),
                    "entity_id": entity_id,
                    "attr": attr,
                    "value": fact.value,
                    "is_null": fact.value is None,
                    "raw_event_id": fact.raw_event_id,
                    "observed_at": fact.observed_at,
                }
            )
    if entity_rows:
        await session.execute(Entity.__table__.insert(), entity_rows)
    if fact_rows:
        await session.execute(EntityFact.__table__.insert(), fact_rows)

    live_canonical = {f.canonical_id for f in folded}
    canonical_rows, member_rows = [], []
    for cluster in clusters:
        if cluster.canonical_id not in live_canonical:
            continue
        canonical_rows.append(
            {
                "canonical_id": cluster.canonical_id,
                "entity_type": cluster.entity_type,
                "anchor_key": cluster.anchor_key,
                "minted_seq": cluster.minted_order,
                "member_count": len(cluster.members),
            }
        )
        for key, evidence in sorted(cluster.members.items()):
            member_rows.append(
                {
                    "id": _uuid("member", entity_ids[key]),
                    "canonical_id": cluster.canonical_id,
                    "entity_id": entity_ids[key],
                    "evidence": evidence[:256],
                }
            )
    if canonical_rows:
        await session.execute(EntityCanonical.__table__.insert(), canonical_rows)
    if member_rows:
        await session.execute(CanonicalMember.__table__.insert(), member_rows)

    alias_rows = [
        {"alias_id": alias, "canonical_id": target, "reason": "merged"}
        for alias, target in sorted(aliases.items(), key=lambda p: str(p[0]))
    ]
    alias_rows += [
        {"alias_id": cid, "canonical_id": cid, "reason": "retired"}
        for cid in sorted(set(retired), key=str)
        if cid not in aliases
    ]
    if alias_rows:
        await session.execute(CanonicalAlias.__table__.insert(), alias_rows)

    if folded:
        await session.execute(
            FactCurrent.__table__.insert(),
            [
                {
                    "id": _uuid("current", fact.canonical_id, fact.attr),
                    "canonical_id": fact.canonical_id,
                    "entity_type": fact.entity_type,
                    "attr": fact.attr,
                    "value": fact.value,
                    "value_num": fact.value_num,
                    "entity_id": entity_ids.get(fact.entity_key),
                    "raw_event_id": fact.raw_event_id,
                    "observed_at": fact.observed_at,
                    "disagreements": fact.disagreements,
                }
                for fact in sorted(folded, key=lambda f: (str(f.canonical_id), f.attr))
            ],
        )

    if edges:
        await session.execute(
            CanonicalLink.__table__.insert(),
            [
                {
                    "id": _uuid(
                        "link", edge.from_canonical, edge.rel, edge.to_canonical
                    ),
                    "from_canonical": edge.from_canonical,
                    "rel": edge.rel,
                    "to_canonical": edge.to_canonical,
                    "grounding": edge.grounding,
                }
                for edge in edges
            ],
        )


async def prune(session) -> None:
    keep = (
        (
            await session.execute(
                select(EngineRun.seq)
                .order_by(EngineRun.seq.desc())
                .limit(settings.ENGINE_RUN_RETENTION)
            )
        )
        .scalars()
        .all()
    )
    await session.execute(delete(EngineRun).where(EngineRun.seq < min(keep)))
