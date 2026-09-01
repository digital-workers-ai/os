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
    "salesforce",
    "shopify",
    "woocommerce",
    "mailchimp",
    "twilio",
    "google_sheets",
]


async def _rebuilt(session, sessionmaker_for_test):
    synced = await sync.run_all(sessionmaker_for_test, SOURCES)
    assert synced["failed"] == 0, synced
    return await run.rebuild(session)


async def test_the_sync_stores_the_whole_fourteen_source_estate(
    session, sessionmaker_for_test
):
    result = await sync.run_all(sessionmaker_for_test, SOURCES)
    assert result["failed"] == 0, result
    assert result["rows_written"] == 281

    total = (
        await session.execute(select(func.count()).select_from(RawEvent))
    ).scalar_one()
    assert total == 281


async def test_the_rebuild_resolves_the_batch_two_entities(
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
        "person": 23,
        "deal": 28,
        "subscription": 10,
        "ticket": 20,
        "order": 4,
        "product": 4,
        "message": 3,
        "email_campaign": 27,
        "event": 10,
        "meeting": 5,
        "audience": 6,
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
    assert report["clears"]["phone/salesforce"] == 6
    assert report["clears"]["sent_at/sendgrid"] == 2
    assert report["clears"]["sent_at/mailchimp"] == 2
    assert report["clears"]["industry/zendesk"] == 1
    assert report["clears"]["title/klaviyo"] == 1
    assert report["clears"]["title/salesforce"] == 1

    assert report["counts"]["observed_at_fallback/salesforce"] == 42
    assert report["counts"]["observed_at_fallback/mailchimp"] == 10
    assert report["counts"]["observed_at_fallback/google_sheets"] == 8
    assert report["counts"]["observed_at_fallback/woocommerce"] == 4


async def test_the_batch_two_links_land_with_no_quarantines(
    session, sessionmaker_for_test
):
    result = await _rebuilt(session, sessionmaker_for_test)
    rates = result["report"]["match_rates"]

    assert rates["deal belongs_to company"]["edges"] == 10
    assert rates["deal belongs_to company"]["match_rate"] == 1.0
    assert rates["order placed_by person"]["edges"] == 4
    assert rates["message sent_to person"]["edges"] == 3
    assert result["report"]["quarantines"] == []

    by_rel = dict(
        (
            await session.execute(
                select(CanonicalLink.rel, func.count()).group_by(CanonicalLink.rel)
            )
        ).all()
    )
    assert by_rel == {
        "belongs_to": 30,
        "raised_by": 20,
        "performed_by": 10,
        "attended_by": 5,
        "placed_by": 4,
        "sent_to": 3,
    }
