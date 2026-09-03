import pytest
import pytest_asyncio
from sqlalchemy import select, text

from app import sync
from app.engine import mappings, run
from app.models import Base, Entity

pytestmark = pytest.mark.e2e

CONNECTED = ["hubspot", "salesforce", "stripe"]


@pytest_asyncio.fixture(scope="module")
async def partial(db_engine, sessionmaker_for_test):
    tables = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
    async with db_engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))

    result = await sync.run_all(sessionmaker_for_test, CONNECTED)
    assert result["failed"] == 0, result
    async with sessionmaker_for_test() as session:
        return await run.rebuild(session)


@pytest_asyncio.fixture
async def session(sessionmaker_for_test, partial):
    async with sessionmaker_for_test() as s:
        yield s


class TestDeadPathsScopeToTheConnectedEstate:
    def test_no_connected_source_has_a_dead_line(self, partial):
        dead = {
            path.split(":", 1)[1].split(".", 1)[0]
            for path in partial["report"]["dead_paths"]
        }
        assert dead.isdisjoint(set(CONNECTED))

    def test_absent_sources_leave_no_dead_lines(self, partial):
        assert partial["report"]["dead_paths"] == []

    async def test_the_unconnected_sources_produce_nothing(self, partial, session):
        present = {
            row[0]
            for row in (await session.execute(select(Entity.source).distinct())).all()
        }
        assert present == set(CONNECTED)
        mapped = {line.source for line in mappings.load()}
        assert len(mapped - present) == 24


class TestPartialEstateIsStillCoherent:
    def test_a_relationship_with_no_candidates_is_absent_not_a_zero_rate(self, partial):
        rates = partial["report"]["match_rates"]
        assert "ticket raised_by person" not in rates
        assert all(entry["candidates"] for entry in rates.values())
        assert all(entry["match_rate"] is not None for entry in rates.values())
        assert rates["subscription belongs_to company"]["match_rate"] == 1.0

    def test_the_mapping_file_is_not_source_scoped(self, partial):
        assert len({line.source for line in mappings.load()}) == 27
