import time

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.enrichment import reader, vocabulary
from app.models import (
    CanonicalAlias,
    EnrichedFact,
    EnrichmentRun,
    EntityCanonical,
    FactCurrent,
)

_LOCK_ID = 0x_E471C4


class EnrichmentError(RuntimeError):
    pass


async def resolve_alias(session, canonical_id):
    seen = set()
    current = canonical_id
    while True:
        if current in seen:
            break
        seen.add(current)
        row = await session.get(CanonicalAlias, current)
        if row is None:
            break
        current = row.canonical_id
    return current


async def reconcile(session, reading) -> int:
    rows = (
        (
            await session.execute(
                select(EnrichedFact).where(EnrichedFact.reading == reading.name)
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return 0

    live = {
        cid
        for (cid,) in (
            await session.execute(select(EntityCanonical.canonical_id))
        ).all()
    }
    moved = 0
    for row in rows:
        if row.canonical_id in live:
            continue
        survivor = await resolve_alias(session, row.canonical_id)
        if survivor in live and survivor != row.canonical_id:
            clash = (
                await session.execute(
                    select(func.count())
                    .select_from(EnrichedFact)
                    .where(
                        EnrichedFact.canonical_id == survivor,
                        EnrichedFact.reading == reading.name,
                        EnrichedFact.attr == row.attr,
                        EnrichedFact.value == row.value,
                    )
                )
            ).scalar_one()
            if clash:
                await session.delete(row)
            else:
                row.canonical_id = survivor
            moved += 1
    if moved:
        await session.commit()
    return moved


async def eligible_count(session, reading) -> int:
    return (
        await session.execute(
            select(func.count())
            .select_from(FactCurrent)
            .where(
                FactCurrent.attr == reading.input_attr,
                FactCurrent.entity_type == reading.entity,
                func.length(func.trim(FactCurrent.value)) > 0,
            )
        )
    ).scalar_one()


async def candidates(
    session, reading, *, force: bool = False, limit: int | None = None
) -> list:
    if limit is not None and limit <= 0:
        return []

    fresh: dict = {}
    if not force:
        fresh = dict(
            (
                await session.execute(
                    select(EnrichedFact.canonical_id, EnrichedFact.input_sha).where(
                        EnrichedFact.reading == reading.name,
                        EnrichedFact.vocabulary_sha == reading.sha,
                    )
                )
            ).all()
        )

    query = (
        select(FactCurrent.canonical_id, FactCurrent.value)
        .join(
            EntityCanonical,
            EntityCanonical.canonical_id == FactCurrent.canonical_id,
        )
        .where(
            FactCurrent.attr == reading.input_attr,
            FactCurrent.entity_type == reading.entity,
            func.length(func.trim(FactCurrent.value)) > 0,
        )
        .order_by(EntityCanonical.minted_seq)
    )
    out: list = []
    page = max(200, limit or 200)
    offset = 0
    while True:
        rows = (await session.execute(query.limit(page).offset(offset))).all()
        if not rows:
            return out
        for canonical_id, value in rows:
            stored = fresh.get(canonical_id)
            if stored is not None and stored == reader.input_sha(value):
                continue
            out.append((canonical_id, value))
            if limit is not None and len(out) >= limit:
                return out
        if len(rows) < page:
            return out
        offset += len(rows)


async def write(session, canonical_id, reading, result) -> int:
    await session.execute(
        delete(EnrichedFact).where(
            EnrichedFact.canonical_id == canonical_id,
            EnrichedFact.reading == reading.name,
        )
    )
    for finding in result.findings:
        session.add(
            EnrichedFact(
                canonical_id=canonical_id,
                entity_type=reading.entity,
                reading=reading.name,
                attr=finding.field,
                value=finding.label,
                quote=finding.quote,
                quote_verified=finding.quote_verified,
                input_sha=result.input_sha,
                vocabulary_sha=result.vocabulary_sha,
                model=result.model,
                prompt_version=result.prompt_version,
            )
        )
    return len(result.findings)


async def enrich(
    session,
    *,
    reading_name: str | None = None,
    force: bool = False,
    limit: int | None = None,
) -> dict:
    if not settings.ENRICHMENT_ENABLED:
        raise EnrichmentError(
            "ENRICHMENT_ENABLED is off. This is the one layer that calls a "
            "model, and it is opt-in on purpose."
        )

    got_lock = (
        await session.execute(select(func.pg_try_advisory_xact_lock(_LOCK_ID)))
    ).scalar_one()
    if not got_lock:
        raise EnrichmentError("an enrichment run is already in progress")

    started = time.monotonic()
    readings = vocabulary.load()
    if reading_name:
        if reading_name not in readings:
            raise EnrichmentError(f"no reading named {reading_name!r}")
        readings = {reading_name: readings[reading_name]}

    cap = limit if limit is not None else settings.ENRICHMENT_MAX_CALLS_PER_RUN
    report = {
        "readings": {},
        "calls": 0,
        "rows": 0,
        "failed": 0,
        "unverified_quotes": 0,
        "reconciled": 0,
    }

    for name, reading in readings.items():
        reconciled = await reconcile(session, reading)
        eligible = await eligible_count(session, reading)
        pending = await candidates(session, reading, force=force, limit=cap)
        truncated = len(pending) >= cap and eligible > len(pending)
        per_reading = {
            "eligible": eligible,
            "pending": len(pending),
            "reconciled": reconciled,
            "read": 0,
            "rows": 0,
            "failed": 0,
            "unverified_quotes": 0,
            "truncated_at_cap": truncated,
            "errors": [],
        }

        if pending:
            results = await reader.read_many(reading, [text for _cid, text in pending])
            for (canonical_id, _text), result in zip(pending, results, strict=True):
                if isinstance(result, reader.ReadError):
                    per_reading["failed"] += 1
                    if len(per_reading["errors"]) < 5:
                        per_reading["errors"].append(str(result))
                    continue
                try:
                    written = await write(session, canonical_id, reading, result)
                    await session.commit()
                except IntegrityError as exc:
                    await session.rollback()
                    per_reading["failed"] += 1
                    per_reading["errors"].append(f"{canonical_id}: {exc.orig}")
                    continue
                per_reading["read"] += 1
                per_reading["rows"] += written
                per_reading["unverified_quotes"] += sum(
                    1 for f in result.findings if not f.quote_verified
                )

        session.add(
            EnrichmentRun(
                reading=name,
                vocabulary_sha=reading.sha,
                model=settings.ENRICHMENT_MODEL,
                prompt_version=reader.PROMPT_VERSION,
                read=per_reading["read"],
                failed=per_reading["failed"],
                truncated_at_cap=truncated,
            )
        )
        await session.commit()

        report["readings"][name] = per_reading
        report["calls"] += per_reading["read"] + per_reading["failed"]
        report["rows"] += per_reading["rows"]
        report["failed"] += per_reading["failed"]
        report["unverified_quotes"] += per_reading["unverified_quotes"]
        report["reconciled"] += reconciled
        cap -= per_reading["read"] + per_reading["failed"]
        if cap <= 0:
            report["truncated_at_cap"] = True
            break

    report["duration_ms"] = int((time.monotonic() - started) * 1000)
    return report


async def coverage(session, reading) -> dict:
    eligible = await eligible_count(session, reading)
    read = (
        await session.execute(
            select(func.count(func.distinct(EnrichedFact.canonical_id)))
            .join(
                EntityCanonical,
                EntityCanonical.canonical_id == EnrichedFact.canonical_id,
            )
            .where(
                EnrichedFact.reading == reading.name,
                EnrichedFact.vocabulary_sha == reading.sha,
            )
        )
    ).scalar_one()
    stale = (
        await session.execute(
            select(func.count(func.distinct(EnrichedFact.canonical_id)))
            .join(
                EntityCanonical,
                EntityCanonical.canonical_id == EnrichedFact.canonical_id,
            )
            .where(
                EnrichedFact.reading == reading.name,
                EnrichedFact.vocabulary_sha != reading.sha,
            )
        )
    ).scalar_one()
    last = (
        (
            await session.execute(
                select(EnrichmentRun)
                .where(EnrichmentRun.reading == reading.name)
                .order_by(EnrichmentRun.seq.desc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    return {
        "reading": reading.name,
        "vocabulary_sha": reading.sha[:12],
        "eligible": eligible,
        "read_under_current_vocabulary": read,
        "read_under_a_retired_vocabulary": stale,
        "never_read": max(0, eligible - read - stale),
        "last_run": None
        if last is None
        else {
            "at": last.created_at.isoformat(),
            "read": last.read,
            "failed": last.failed,
            "truncated_at_cap": last.truncated_at_cap,
            "model": last.model,
            "prompt_version": last.prompt_version,
        },
    }


async def for_entity(session, canonical_id) -> list:
    resolved = await resolve_alias(session, canonical_id)
    rows = (
        (
            await session.execute(
                select(EnrichedFact)
                .where(EnrichedFact.canonical_id.in_({canonical_id, resolved}))
                .order_by(EnrichedFact.reading, EnrichedFact.attr, EnrichedFact.value)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "reading": r.reading,
            "attr": r.attr,
            "value": r.value,
            "quote": r.quote,
            "quote_verified": r.quote_verified,
            "model": r.model,
            "prompt_version": r.prompt_version,
            "vocabulary_sha": r.vocabulary_sha[:12],
            "input_sha": r.input_sha[:12],
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
