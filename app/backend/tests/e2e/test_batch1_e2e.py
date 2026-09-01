import pytest
from sqlalchemy import func, select

from app import sync
from app.engine import run
from app.models import CanonicalLink, EntityCanonical, RawEvent

pytestmark = pytest.mark.e2e

SOURCES = [
    "hubspot",
    "stripe",
    "zendesk",
    "intercom",
    "klaviyo",
    "calendly",
    "sendgrid",
    "customerio",
]


async def _rebuilt(session, sessionmaker_for_test):
    synced = await sync.run_all(sessionmaker_for_test, SOURCES)
    assert synced["failed"] == 0, synced
    return await run.rebuild(session)


async def test_the_sync_stores_the_whole_eight_source_estate(
    session, sessionmaker_for_test
):
    result = await sync.run_all(sessionmaker_for_test, SOURCES)
    assert result["failed"] == 0, result
    assert result["rows_written"] == 206

    total = (
        await session.execute(select(func.count()).select_from(RawEvent))
    ).scalar_one()
    assert total == 206


async def test_the_rebuild_resolves_the_batch_one_entities(
    session, sessionmaker_for_test
):
    result = await _rebuilt(session, sessionmaker_for_test)
    assert result["ok"] is True

    canonical_by_type = dict(
        (
            await session.execute(
                select(EntityCanonical.entity_type, func.count()).group_by(
                    EntityCanonical.entity_type
                )
            )
        ).all()
    )
    assert canonical_by_type == {
        "company": 10,
        "person": 22,
        "deal": 10,
        "subscription": 10,
        "ticket": 20,
        "email_campaign": 19,
        "event": 10,
        "meeting": 5,
        "audience": 4,
    }


async def test_the_estate_is_clean_apart_from_its_counted_clears(
    session, sessionmaker_for_test
):
    report = (await _rebuilt(session, sessionmaker_for_test))["report"]
    assert report["skips"] == {}
    assert report["dead_paths"] == []
    assert report["records_skipped"] == {}

    assert report["clears"]["phone/zendesk"] == 6
    assert report["clears"]["phone/intercom"] == 6
    assert report["clears"]["phone/klaviyo"] == 6
    assert report["clears"]["phone/sendgrid"] == 3
    assert report["clears"]["sent_at/sendgrid"] == 2
    assert report["clears"]["industry/zendesk"] == 1
    assert report["clears"]["title/klaviyo"] == 1

    assert report["counts"]["observed_at_fallback/customerio"] == 12


async def test_the_batch_one_links_all_land_with_no_quarantines(
    session, sessionmaker_for_test
):
    result = await _rebuilt(session, sessionmaker_for_test)
    rates = result["report"]["match_rates"]

    assert rates["ticket belongs_to company"]["edges"] == 10
    assert rates["ticket raised_by person"]["edges"] == 20
    assert rates["event performed_by person"]["edges"] == 10
    assert rates["meeting attended_by person"]["edges"] == 5
    assert all(rate["match_rate"] == 1.0 for rate in rates.values())
    assert result["report"]["quarantines"] == []

    by_rel = dict(
        (
            await session.execute(
                select(CanonicalLink.rel, func.count()).group_by(CanonicalLink.rel)
            )
        ).all()
    )
    assert by_rel == {
        "belongs_to": 20,
        "raised_by": 20,
        "performed_by": 10,
        "attended_by": 5,
    }
