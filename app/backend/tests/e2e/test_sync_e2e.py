import pytest
from sqlalchemy import func, select

from app import sync
from app.models import PullManifest, RawEvent

pytestmark = pytest.mark.e2e


async def test_the_first_sync_stores_the_whole_estate(session, sessionmaker_for_test):
    result = await sync.run_all(sessionmaker_for_test, ["hubspot"])
    assert result["failed"] == 0, result

    counts = dict(
        (
            await session.execute(
                select(RawEvent.object_type, func.count()).group_by(
                    RawEvent.object_type
                )
            )
        ).all()
    )
    assert counts == {"companies": 10, "contacts": 22, "deals": 10}
    assert result["rows_written"] == 42


async def test_a_second_sync_of_an_unchanged_estate_writes_nothing(
    session, sessionmaker_for_test
):
    first = await sync.run_all(sessionmaker_for_test, ["hubspot"])
    assert first["rows_written"] == 42
    second = await sync.run_all(sessionmaker_for_test, ["hubspot"])
    assert second["failed"] == 0, second
    assert second["rows_written"] == 0

    total = (
        await session.execute(select(func.count()).select_from(RawEvent))
    ).scalar_one()
    assert total == 42


async def test_the_manifests_name_every_id_that_was_pulled(
    session, sessionmaker_for_test
):
    result = await sync.run_all(sessionmaker_for_test, ["hubspot"])
    assert result["failed"] == 0, result

    rows = (await session.execute(select(PullManifest))).scalars().all()
    sizes = {(r.source, r.object_type): len(r.source_ids) for r in rows}
    assert sizes == {
        ("hubspot", "companies"): 10,
        ("hubspot", "contacts"): 22,
        ("hubspot", "deals"): 10,
    }
    for row in rows:
        assert len(set(row.source_ids)) == len(row.source_ids)
