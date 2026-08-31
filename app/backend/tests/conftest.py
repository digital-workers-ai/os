import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models import Base

TEST_DB_SUFFIX = "_test"


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
