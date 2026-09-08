import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models import Base, Entity

TEST_DB_SUFFIX = "_test"
FIXTURE_SEEN = datetime(2026, 8, 1, tzinfo=UTC)
NOW = datetime(2026, 9, 4, 12, tzinfo=UTC)


def _split_url(url: str) -> tuple[str, str]:
    base, _, name = url.rpartition("/")
    return base, name


def test_database_url() -> str:
    base, name = _split_url(settings.DATABASE_URL)
    return f"{base}/{name}{TEST_DB_SUFFIX}"


def admin_database_url() -> str:
    base, _name = _split_url(settings.DATABASE_URL)
    return f"{base}/postgres"


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    _base, name = _split_url(test_database_url())
    admin = create_async_engine(admin_database_url(), isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        await conn.execute(text(f'CREATE DATABASE "{name}"'))
    await admin.dispose()

    engine = create_async_engine(test_database_url(), pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def sessionmaker_for_test(db_engine):
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def session(db_engine, sessionmaker_for_test):
    tables = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
    async with db_engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    async with sessionmaker_for_test() as s:
        yield s


@pytest_asyncio.fixture
async def canonical(session):
    from app.models import CanonicalMember, EntityCanonical, EntityFact, FactCurrent

    counter = {"n": 0}

    async def _make(entity_type: str, facts: dict, sources=None, member_facts=None):
        counter["n"] += 1
        anchor = f"test|{entity_type}|{counter['n']}"
        canonical_id = uuid.uuid5(uuid.NAMESPACE_URL, anchor)
        sources = sources or ["hubspot"]
        member_facts = member_facts or {}
        session.add(
            EntityCanonical(
                canonical_id=canonical_id,
                entity_type=entity_type,
                anchor_key=anchor,
                minted_seq=counter["n"],
                member_count=len(sources),
            )
        )
        entity_ids = []
        for source in sources:
            entity_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{anchor}|{source}")
            entity_ids.append(entity_id)
            session.add(
                Entity(
                    id=entity_id,
                    source=source,
                    entity_type=entity_type,
                    source_id=f"{entity_type}_{counter['n']}",
                    object_type=f"{entity_type}s",
                    first_seq=counter["n"],
                )
            )
        await session.flush()
        for source, entity_id in zip(sources, entity_ids, strict=True):
            session.add(
                CanonicalMember(
                    id=uuid.uuid5(uuid.NAMESPACE_URL, f"{anchor}|{source}|member"),
                    canonical_id=canonical_id,
                    entity_id=entity_id,
                )
            )
            for attr, value in {**facts, **member_facts.get(source, {})}.items():
                session.add(
                    EntityFact(
                        id=uuid.uuid5(uuid.NAMESPACE_URL, f"{anchor}|{source}|{attr}"),
                        entity_id=entity_id,
                        attr=attr,
                        value=None if value is None else str(value),
                        is_null=value is None,
                        observed_at=FIXTURE_SEEN,
                    )
                )
        for attr, value in facts.items():
            number = None
            try:
                number = float(value)
            except (TypeError, ValueError):
                pass
            session.add(
                FactCurrent(
                    id=uuid.uuid5(uuid.NAMESPACE_URL, f"{anchor}|{attr}"),
                    canonical_id=canonical_id,
                    entity_type=entity_type,
                    attr=attr,
                    value=str(value),
                    value_num=number,
                    entity_id=entity_ids[0],
                    observed_at=FIXTURE_SEEN,
                    disagreements=max(0, len(sources) - 1),
                )
            )
        await session.flush()
        return canonical_id

    return _make


@pytest_asyncio.fixture
async def link(session):
    from app.models import CanonicalLink

    async def _make(from_canonical, rel: str, to_canonical, grounding="via:test"):
        session.add(
            CanonicalLink(
                id=uuid.uuid5(
                    uuid.NAMESPACE_URL, f"{from_canonical}|{rel}|{to_canonical}"
                ),
                from_canonical=from_canonical,
                rel=rel,
                to_canonical=to_canonical,
                grounding=grounding,
            )
        )
        await session.flush()

    return _make


@pytest.fixture
def statements(db_engine):
    from contextlib import contextmanager

    from sqlalchemy import event

    @contextmanager
    def _capturing():
        seen: list[str] = []

        def _on_execute(conn, cursor, statement, params, context, many):
            seen.append(statement)

        event.listen(db_engine.sync_engine, "before_cursor_execute", _on_execute)
        try:
            yield seen
        finally:
            event.remove(db_engine.sync_engine, "before_cursor_execute", _on_execute)

    return _capturing


@pytest.fixture
def count_queries(db_engine):
    from contextlib import contextmanager

    from sqlalchemy import event

    class Counter:
        total = 0

    @contextmanager
    def _counting():
        counter = Counter()

        def _on_execute(conn, cursor, statement, params, context, many):
            counter.total += 1

        event.listen(db_engine.sync_engine, "before_cursor_execute", _on_execute)
        try:
            yield counter
        finally:
            event.remove(db_engine.sync_engine, "before_cursor_execute", _on_execute)

    return _counting
