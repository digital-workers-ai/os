import pytest
from sqlalchemy import text

import app.db
import app.main
from app.config import Settings
from app.models import RawEvent


def test_database_url_default_points_at_the_stack():
    default = Settings.model_fields["DATABASE_URL"].default
    assert default == "postgresql+asyncpg://os:os@localhost:5442/os_v0"


def test_settings_read_the_environment(monkeypatch):
    url = "postgresql+asyncpg://x:x@x:1/x"
    monkeypatch.setenv("DATABASE_URL", url)
    assert Settings(_env_file=None).DATABASE_URL == url


async def test_the_dependency_yields_a_usable_session(db_engine):
    dependency = app.db.get_session()
    session = await dependency.__anext__()
    assert await session.scalar(text("SELECT 1")) == 1
    with pytest.raises(StopAsyncIteration):
        await dependency.__anext__()


async def test_creating_the_schema_is_idempotent():
    await app.db.create_schema()
    await app.db.create_schema()


async def test_startup_creates_the_schema():
    async with app.main.lifespan(app.main.app):
        pass


def _raw_event(index):
    return RawEvent(
        source="s",
        object_type="o",
        source_id=f"id-{index}",
        raw_payload={},
        payload_sha=f"sha-{index}",
    )


async def test_seq_orders_inserts_within_one_transaction(session):
    events = [_raw_event(index) for index in range(3)]
    for event in events:
        session.add(event)
        await session.flush()
        await session.refresh(event)
    seqs = [event.seq for event in events]
    assert seqs[0] < seqs[1] < seqs[2]


async def test_server_timestamps_are_timezone_aware(session):
    event = _raw_event(0)
    session.add(event)
    await session.flush()
    await session.refresh(event)
    assert event.ingested_at.tzinfo is not None


def test_reset_all_clears_every_registered_cache():
    from app import caches
    from app.engine import transforms
    from app.sources import hooks, registry

    registry.discover()
    hooks.hooks()
    transforms.load_synonyms()
    caches.reset_all()
    assert registry._cache is None
    assert hooks._cache is None
    assert transforms._synonyms_cache is None


async def test_a_snapshot_past_the_window_is_pruned(session, monkeypatch):
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from app.config import settings
    from app.engine import run
    from app.models import EngineRun, MetricSnapshot

    monkeypatch.setattr(settings, "SNAPSHOT_RETENTION_DAYS", 400)
    now = datetime.now(UTC)
    session.add(EngineRun(ok=True, report={}))
    session.add(
        MetricSnapshot(metric="mrr", value=1.0, recorded_at=now - timedelta(days=401))
    )
    session.add(
        MetricSnapshot(metric="mrr", value=2.0, recorded_at=now - timedelta(days=399))
    )
    await session.flush()

    await run.prune(session)

    kept = (await session.execute(select(MetricSnapshot))).scalars().all()
    assert [r.value for r in kept] == [2.0]
