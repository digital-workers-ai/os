import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.models import Base

target_metadata = Base.metadata


def render_item(type_, obj, autogen_context):
    if type_ == "type" and type(obj).__module__.startswith("pgvector"):
        autogen_context.imports.add("import pgvector.sqlalchemy")
        return f"pgvector.sqlalchemy.Vector({obj.dim})"
    return False


def run(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_on_own_engine():
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.connect() as connection:
        await connection.run_sync(run)
    await engine.dispose()


connection = context.config.attributes.get("connection")
if connection is not None:
    run(connection)
else:
    asyncio.run(run_on_own_engine())
