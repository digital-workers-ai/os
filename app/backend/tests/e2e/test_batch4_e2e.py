import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select

from app import sync
from app.api import sources_api
from app.db import get_session
from app.engine import run
from app.main import app
from app.models import CanonicalLink, EntityCanonical, RawEvent
from app.sources import registry

pytestmark = pytest.mark.e2e

SOURCES = sorted(registry.discover())


@pytest_asyncio.fixture
async def api(session, sessionmaker_for_test, monkeypatch):
    async def override():
        yield session

    app.dependency_overrides[get_session] = override
    monkeypatch.setattr(
        sources_api, "async_session", sessionmaker_for_test, raising=False
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://backend"
    ) as client:
        yield client
    app.dependency_overrides.clear()


async def _rebuilt(session, sessionmaker_for_test):
    synced = await sync.run_all(sessionmaker_for_test, SOURCES)
    assert synced["failed"] == 0, synced
    return await run.rebuild(session)


async def test_the_sync_stores_the_whole_twenty_seven_source_estate(
    session, sessionmaker_for_test
):
    result = await sync.run_all(sessionmaker_for_test, SOURCES)
    assert result["failed"] == 0, result
    assert result["rows_written"] == 382
    assert all(r["truncated"] is False for r in result["results"]), result

    total = (
        await session.execute(select(func.count()).select_from(RawEvent))
    ).scalar_one()
    assert total == 382


async def test_the_rebuild_resolves_the_batch_four_entities(
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
        "email_campaign": 35,
        "event": 42,
        "event_definition": 4,
        "ad_account": 8,
        "meeting": 11,
        "audience": 6,
        "campaign": 8,
        "traffic_report": 6,
        "data_source": 3,
    }
    assert sum(canonical_by_type.values()) == 225


async def test_the_estate_is_clean_apart_from_its_counted_clears(
    session, sessionmaker_for_test
):
    report = (await _rebuilt(session, sessionmaker_for_test))["report"]
    assert report["skips"] == {}
    assert report["dead_paths"] == []
    assert report["records_skipped"] == {}
    assert report["quarantines"] == []

    assert report["clears"]["phone/zendesk"] == 6
    assert report["clears"]["phone/intercom"] == 6
    assert report["clears"]["phone/klaviyo"] == 6
    assert report["clears"]["phone/sendgrid"] == 3
    assert report["clears"]["phone/salesforce"] == 6
    assert report["clears"]["phone/activecampaign"] == 6
    assert report["clears"]["sent_at/sendgrid"] == 2
    assert report["clears"]["sent_at/mailchimp"] == 2
    assert report["clears"]["sent_at/activecampaign"] == 2
    assert report["clears"]["industry/zendesk"] == 1
    assert report["clears"]["title/klaviyo"] == 1
    assert report["clears"]["title/salesforce"] == 1

    assert report["counts"]["observed_at_fallback/salesforce"] == 42
    assert report["counts"]["observed_at_fallback/mailchimp"] == 10
    assert report["counts"]["observed_at_fallback/google_sheets"] == 8
    assert report["counts"]["observed_at_fallback/woocommerce"] == 4
    assert report["counts"]["observed_at_fallback/meta"] == 4
    assert report["counts"]["observed_at_fallback/google_ads"] == 4
    assert report["counts"]["observed_at_fallback/google_analytics"] == 6
    assert report["counts"]["observed_at_fallback/smartlook"] == 4
    assert report["counts"]["multi_object_entity/meta/campaign"] == 4
    assert report["counts"]["account_currency/meta"] == 4
    assert report["counts"]["account_currency/google_ads"] == 4


async def test_the_analytics_events_link_to_their_people(
    session, sessionmaker_for_test
):
    await _rebuilt(session, sessionmaker_for_test)

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
        "performed_by": 26,
        "attended_by": 11,
        "placed_by": 4,
        "sent_to": 3,
        "held_with": 6,
    }
    assert sum(by_rel.values()) == 100


async def test_the_sources_endpoint_reflects_the_finished_sync(
    api, session, sessionmaker_for_test
):
    synced = await sync.run_all(sessionmaker_for_test, SOURCES)
    assert synced["failed"] == 0, synced

    rows = (await api.get("/api/sources")).json()["sources"]
    assert len(rows) == 27
    assert all(row["last_attempt"] is not None for row in rows), rows
