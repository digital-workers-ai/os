import time
import uuid

from sqlalchemy import delete, func, select

from app.config import settings
from app.connectors import registry
from app.engine import mappings, ontology, pipeline, transforms
from app.engine.report import SyncReport
from app.models import EngineRun, Entity, EntityFact
from app.store import first_seen_query, latest_rows_query

NAMESPACE = uuid.UUID("6b1c9f4e-0a2d-5f83-9c17-0d4e6a8b2f10")

_REBUILD_LOCK_ID = 0x_5EB1D


class RebuildInProgress(RuntimeError):
    pass


def _uuid(*parts) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, "|".join(str(p) for p in parts))


async def _clear_projection(session) -> None:
    for table in (EntityFact, Entity):
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

    await _write(session, projected)

    for entity in projected.values():
        report.count(f"records/{entity.source}/{entity.entity_type}")

    facts_written = sum(len(e.facts) for e in projected.values())
    duration_ms = int((time.monotonic() - started) * 1000)
    run = EngineRun(
        ok=True,
        raw_events_read=len(rows),
        entities_written=len(projected),
        facts_written=facts_written,
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
        "facts": facts_written,
        "report": report.as_dict(),
    }


async def _write(session, projected: dict) -> None:
    await _clear_projection(session)

    entity_rows, fact_rows = [], []
    for _key, entity in sorted(projected.items()):
        entity_id = _uuid("entity", entity.anchor_key)
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
