from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session():
    async with async_session() as session:
        yield session


def alembic_config(connection) -> Config:
    config = Config(ALEMBIC_INI)
    config.attributes["connection"] = connection
    return config


def migrate(connection) -> None:
    command.upgrade(alembic_config(connection), "head")


async def create_schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(migrate)
