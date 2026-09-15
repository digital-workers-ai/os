from sqlalchemy import func, select

from app.models import Entity, SyncRun
from app.sources import catalog
from app.studio import swipe


async def estate(session):
    rows = (
        await session.execute(
            select(SyncRun.source, SyncRun.ok, SyncRun.started_at, SyncRun.detail)
            .distinct(SyncRun.source)
            .order_by(SyncRun.source, SyncRun.started_at.desc())
        )
    ).all()
    status = {row.source: row for row in rows}
    counted = dict(
        (
            await session.execute(
                select(Entity.source, func.count()).group_by(Entity.source)
            )
        ).all()
    )
    watched = set(swipe.competitor_sources())
    entries = catalog.catalog()
    return {
        "competitor_sources": [
            _source(entry, status.get(entry["source"]), counted.get(entry["source"], 0))
            for entry in entries
            if entry["source"] in watched
        ],
        "estate_sources": sum(1 for entry in entries if entry["source"] not in watched),
    }


def _source(entry, run, rows):
    return {
        "source": entry["source"],
        "label": entry["label"],
        "ok": run.ok if run else False,
        "last_sync": run.started_at.isoformat() if run else None,
        "rows": rows,
        "detail": entry["unlocks"],
        "error": run.detail if run and not run.ok else None,
    }
