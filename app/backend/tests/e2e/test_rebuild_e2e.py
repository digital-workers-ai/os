import pytest
from sqlalchemy import func, select

from app import sync
from app.engine import run
from app.models import Entity, EntityFact

pytestmark = pytest.mark.e2e


async def _rebuilt(session, sessionmaker_for_test):
    synced = await sync.run_all(sessionmaker_for_test, ["hubspot"])
    assert synced["failed"] == 0, synced
    return await run.rebuild(session)


async def test_the_rebuild_projects_the_whole_estate(session, sessionmaker_for_test):
    result = await _rebuilt(session, sessionmaker_for_test)
    assert result["ok"] is True

    by_type = dict(
        (
            await session.execute(
                select(Entity.entity_type, func.count()).group_by(Entity.entity_type)
            )
        ).all()
    )
    assert by_type == {"company": 10, "person": 22, "deal": 10}

    facts_by_type = dict(
        (
            await session.execute(
                select(Entity.entity_type, func.count())
                .select_from(EntityFact)
                .join(Entity, Entity.id == EntityFact.entity_id)
                .group_by(Entity.entity_type)
            )
        ).all()
    )
    assert facts_by_type == {"company": 30, "person": 44, "deal": 50}
    assert sum(facts_by_type.values()) == 124


async def test_cyberdynes_empty_industry_is_the_only_clear(
    session, sessionmaker_for_test
):
    result = await _rebuilt(session, sessionmaker_for_test)
    assert result["report"]["clears"] == {"industry/hubspot": 1}


async def test_a_clean_estate_reports_no_skips_dead_paths_or_fallbacks(
    session, sessionmaker_for_test
):
    report = (await _rebuilt(session, sessionmaker_for_test))["report"]
    assert report["skips"] == {}
    assert report["dead_paths"] == []
    assert report["counts"]["account_currency/hubspot"] == 10
    assert "observed_at_fallback/hubspot" not in report["counts"]


async def test_a_second_rebuild_mints_byte_identical_entity_ids(
    session, sessionmaker_for_test
):
    await _rebuilt(session, sessionmaker_for_test)
    before = sorted((await session.execute(select(Entity.id))).scalars().all())

    async with sessionmaker_for_test() as second:
        await run.rebuild(second)
    after = sorted((await session.execute(select(Entity.id))).scalars().all())

    assert len(before) == 42
    assert before == after
