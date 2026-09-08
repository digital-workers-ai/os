import ast
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app import db
from app.models import Base
from tests import conftest

MIGRATIONS = Path(__file__).resolve().parents[1] / "alembic"
EXTENSIONS = {"vector", "pg_trgm"}
DEFINITIONS = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
PUBLIC_TABLES = (
    "select table_name from information_schema.tables where table_schema = 'public'"
)


def _diff_against_models(connection):
    context = MigrationContext.configure(
        connection, opts={"compare_type": True, "compare_server_default": True}
    )
    return compare_metadata(context, Base.metadata)


def _head(connection):
    return ScriptDirectory.from_config(db.alembic_config(connection)).get_current_head()


def _downgrade_to_base(connection):
    command.downgrade(db.alembic_config(connection), "base")


async def _versions(conn):
    rows = await conn.execute(text("select version_num from alembic_version"))
    return [row[0] for row in rows]


async def _public_tables(conn):
    rows = await conn.execute(text(PUBLIC_TABLES))
    return {row[0] for row in rows}


async def _extensions(conn):
    rows = await conn.execute(text("select extname from pg_extension"))
    return {row[0] for row in rows}


class TestMigrations:
    async def test_head_matches_the_models(self, db_engine):
        async with db_engine.connect() as conn:
            assert await conn.run_sync(_diff_against_models) == []

    async def test_a_fresh_database_is_built_and_torn_down_by_the_migrations_alone(
        self,
    ):
        url = conftest.test_database_url() + "_fresh"
        name = url.rpartition("/")[2]
        expected = set(Base.metadata.tables)
        admin = create_async_engine(
            conftest.admin_database_url(), isolation_level="AUTOCOMMIT"
        )
        async with admin.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
            await conn.execute(text(f'CREATE DATABASE "{name}"'))
        engine = create_async_engine(url)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(db.migrate)
                assert await _versions(conn) == [await conn.run_sync(_head)]
                assert expected <= await _public_tables(conn)
                assert EXTENSIONS <= await _extensions(conn)
            async with engine.begin() as conn:
                await conn.run_sync(_downgrade_to_base)
                assert expected.isdisjoint(await _public_tables(conn))
            async with engine.begin() as conn:
                await conn.run_sync(db.migrate)
                assert expected <= await _public_tables(conn)
        finally:
            await engine.dispose()
            async with admin.connect() as conn:
                await conn.execute(
                    text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
                )
            await admin.dispose()

    async def test_the_schema_stage_lands_the_app_database_at_head(self):
        await db.create_schema()
        async with db.engine.connect() as conn:
            assert await _versions(conn) == [await conn.run_sync(_head)]

    def test_migration_files_carry_no_comments(self):
        files = sorted(MIGRATIONS.rglob("*.py"))
        assert files
        assert any(path.parent.name == "versions" for path in files)
        for path in files:
            source = path.read_text()
            commented = [
                line for line in source.splitlines() if line.lstrip().startswith("#")
            ]
            assert commented == [], path
            tree = ast.parse(source)
            assert ast.get_docstring(tree) is None, path
            for node in ast.walk(tree):
                if isinstance(node, DEFINITIONS):
                    assert ast.get_docstring(node) is None, path
