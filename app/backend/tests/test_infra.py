from pathlib import Path

import pytest
from sqlalchemy import select, text

import app.db
import app.main
from app.config import Settings, settings
from app.engine import run
from app.models import EngineRun, RawEvent
from tests import ground_truth


def test_database_url_default_points_at_the_stack():
    default = Settings.model_fields["DATABASE_URL"].default
    assert default == "postgresql+asyncpg://os:os@localhost:5442/os"


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


def _counting_loader():
    calls = {"n": 0}

    def load():
        calls["n"] += 1
        return {"loads": calls["n"]}

    return load


def test_cached_reads_the_loader_once():
    from app import caches

    get = caches.cached(_counting_loader())
    assert get() == {"loads": 1}
    assert get() == {"loads": 1}


def test_reset_all_makes_a_cached_loader_run_again():
    from app import caches

    get = caches.cached(_counting_loader())
    assert get() == {"loads": 1}
    caches.reset_all()
    assert get() == {"loads": 2}


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


async def test_a_rebuild_clears_every_registered_cache(session):
    from app import caches

    get = caches.cached(_counting_loader())
    assert get() == {"loads": 1}
    await run.rebuild(session, run_checks=False)
    assert get() == {"loads": 2}


def test_the_adversarial_corpus_is_mounted_so_its_suite_cannot_silently_skip():
    root = Path(ground_truth.ADVERSARIAL_ROOT)
    assert (root / "seeds").is_dir(), (
        f"{ground_truth.ADVERSARIAL_ROOT}/seeds is absent inside the stack — "
        "restart the backend so docker-compose.yml mounts ../mock there"
    )
    assert (root / "seeds" / "adversarial.py").is_file()


def test_the_er_settings_ship_their_defaults():
    assert Settings.model_fields["ER_BUCKET_CAP"].default == 50
    assert Settings.model_fields["ER_ONE_RECORD_PER_SOURCE"].default is True


async def test_the_rebuild_passes_the_er_settings_to_resolve(session, monkeypatch):
    captured = {}

    def capture(records, onto, report, **kwargs):
        captured.update(kwargs)
        return {"clusters": [], "aliases": {}, "of_record": {}}

    monkeypatch.setattr(run.resolver, "resolve", capture)
    await run.rebuild(session, run_checks=False)
    assert captured == {
        "bucket_cap": settings.ER_BUCKET_CAP,
        "one_record_per_source": settings.ER_ONE_RECORD_PER_SOURCE,
    }


async def test_only_the_newest_engine_runs_survive(session, monkeypatch):
    monkeypatch.setattr(settings, "ENGINE_RUN_RETENTION", 3)
    for n in range(5):
        session.add(EngineRun(ok=True, raw_events_read=n, report={}))
    await session.flush()

    await run.prune(session)

    kept = (await session.execute(select(EngineRun))).scalars().all()
    assert sorted(r.raw_events_read for r in kept) == [2, 3, 4]
