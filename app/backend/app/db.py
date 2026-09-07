from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models import Base

EXTENSIONS = ("vector", "pg_trgm")

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session():
    async with async_session() as session:
        yield session


async def create_schema() -> None:
    async with engine.begin() as conn:
        for name in EXTENSIONS:
            await conn.execute(text(f"CREATE EXTENSION IF NOT EXISTS {name}"))
        await conn.run_sync(Base.metadata.create_all)
