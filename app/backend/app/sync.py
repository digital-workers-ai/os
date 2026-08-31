import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select

from app.config import settings
from app.connectors import registry
from app.connectors.client import collect_stats
from app.models import PullManifest, SyncRun
from app.store import payload_sha, save_raw

logger = logging.getLogger(__name__)


def object_class(module, object_type: str) -> str:
    declared = getattr(module, "OBJECT_CLASS", None) or {}
    return declared.get(object_type, "record")


async def run_connector(source: str, sessionmaker) -> dict:
    module = registry.get(source)

    async with sessionmaker() as session:
        run = SyncRun(source=source, ok=False, started_at=datetime.now(UTC))
        session.add(run)
        await session.commit()
        run_id = run.id

    counts = {"fetched": 0, "written": 0, "refused": 0, "colliding": 0}
    seen: dict[str, list] = {}
    refusals: list[str] = []
    collisions: list[str] = []
    within_pull: dict[tuple, str] = {}

    async def counting_store(
        session, *, source: str, object_type: str, source_id: str, raw_payload: dict
    ):
        counts["fetched"] += 1
        seen.setdefault(object_type, []).append(source_id)
        digest = payload_sha(raw_payload) if isinstance(raw_payload, dict) else None
        previous = within_pull.get((object_type, source_id))
        if digest is not None:
            if previous is not None and previous != digest:
                counts["colliding"] += 1
                if len(collisions) < 5:
                    collisions.append(f"{object_type}/{source_id}")
            within_pull[(object_type, source_id)] = digest
        try:
            written = await save_raw(
                session,
                source=source,
                object_type=object_type,
                source_id=source_id,
                raw_payload=raw_payload,
            )
        except ValueError as exc:
            counts["refused"] += 1
            if len(refusals) < 5:
                refusals.append(f"{object_type}/{source_id}: {exc}")
            return
        if written:
            counts["written"] += 1

    notes: dict | None = None
    error: str | None = None
    stats = collect_stats()
    try:
        async with sessionmaker() as session:
            with stats:
                notes = await module.pull(session, counting_store)
            if not stats.truncated:
                declared = {
                    o
                    for o, cls in (getattr(module, "OBJECT_CLASS", None) or {}).items()
                    if cls == "record"
                }
                for object_type in sorted(declared | set(seen)):
                    if object_class(module, object_type) != "record":
                        continue
                    session.add(
                        PullManifest(
                            source=source,
                            object_type=object_type,
                            source_ids=sorted(set(seen.get(object_type, []))),
                            observed_at=datetime.now(UTC),
                        )
                    )
            await session.commit()
        ok = True
    except Exception as e:
        ok = False
        counts["written"] = 0
        error = f"{type(e).__name__}: {e}"
        logger.warning("sync %s failed: %s", source, error)

    detail_parts = []
    if error:
        detail_parts.append(error)
    if notes:
        detail_parts.append(" ".join(f"{k}={v}" for k, v in sorted(notes.items())))
    if counts["colliding"]:
        detail_parts.append(
            f"{counts['colliding']} id collision(s) inside one pull — two "
            "records shared an id and only the last survives: " + "; ".join(collisions)
        )
    if counts["refused"]:
        detail_parts.append(
            f"{counts['refused']} record(s) refused by the store: "
            + "; ".join(refusals)
        )
    if stats.truncation_reasons:
        detail_parts.append("; ".join(stats.truncation_reasons))
    if stats.truncated:
        detail_parts.append("no manifest written: pull was truncated")
    detail = " | ".join(detail_parts) or None

    async with sessionmaker() as session:
        db_run = await session.get(SyncRun, run_id)
        db_run.ok = ok
        db_run.rows_written = counts["written"]
        db_run.detail = detail
        await session.commit()
        await prune_sync_runs(session)
        await prune_pull_manifests(session)
        await session.commit()

    return {
        "source": source,
        "ok": ok,
        "rows_fetched": counts["fetched"],
        "rows_written": counts["written"],
        "rows_refused": counts["refused"],
        "rows_colliding": counts["colliding"],
        "pages_read": stats.pages_read,
        "truncated": stats.truncated,
        "detail": detail,
    }


async def run_all(sessionmaker, sources: list[str] | None = None) -> dict:
    targets = sorted(sources) if sources else sorted(registry.discover())
    results = [await run_connector(source, sessionmaker) for source in targets]
    ok = sum(1 for r in results if r["ok"])
    return {
        "ok": ok,
        "failed": len(results) - ok,
        "rows_written": sum(r["rows_written"] for r in results),
        "results": results,
    }


async def prune_sync_runs(session) -> None:
    cutoff = datetime.now(UTC) - timedelta(days=settings.SYNC_RUN_RETENTION_DAYS)
    await session.execute(delete(SyncRun).where(SyncRun.started_at < cutoff))


async def prune_pull_manifests(session) -> None:
    ranked = select(
        PullManifest.id,
        func.row_number()
        .over(
            partition_by=(PullManifest.source, PullManifest.object_type),
            order_by=PullManifest.seq.desc(),
        )
        .label("rank"),
    ).subquery()
    stale = select(ranked.c.id).where(ranked.c.rank > settings.PULL_MANIFEST_RETENTION)
    await session.execute(delete(PullManifest).where(PullManifest.id.in_(stale)))
