import math

import httpx
import pytest
import pytest_asyncio

from app import sync
from app.api import entities_api, metrics_api, sources_api
from app.db import get_session
from app.engine import run
from app.main import app

pytestmark = pytest.mark.e2e

SOURCES = ["hubspot", "stripe"]


@pytest_asyncio.fixture
async def api(session, sessionmaker_for_test, monkeypatch):
    async def override():
        yield session

    app.dependency_overrides[get_session] = override
    for module in (sources_api, entities_api, metrics_api):
        monkeypatch.setattr(
            module, "async_session", sessionmaker_for_test, raising=False
        )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://backend"
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def metrics_body(api, session, sessionmaker_for_test):
    synced = await sync.run_all(sessionmaker_for_test, SOURCES)
    assert synced["failed"] == 0, synced
    rebuilt = await run.rebuild(session)
    assert rebuilt["ok"] is True, rebuilt
    response = await api.get("/api/metrics")
    assert response.status_code == 200
    return response.json()["metrics"]


async def test_mrr_measures_the_active_subscriptions(metrics_body):
    row = metrics_body["mrr"]
    assert row["value"] == 17147.0
    assert row["entities"] == 7
    assert row["population_size"] == 10


async def test_contracted_mrr_sums_every_subscription(metrics_body):
    assert metrics_body["contracted_mrr"]["value"] == 20796.0


async def test_avg_mrr_averages_the_active_subscriptions(metrics_body):
    assert metrics_body["avg_mrr"]["value"] == round(17147 / 7, 2)


async def test_subscription_counts(metrics_body):
    assert metrics_body["subscription_count"]["value"] == 10
    assert metrics_body["active_subscriptions"]["value"] == 7


async def test_deal_counts_and_won_value(metrics_body):
    assert metrics_body["deal_count"]["value"] == 10
    row = metrics_body["won_value"]
    assert row["value"] == 227364.0
    assert row["entities"] == 8


async def test_company_counts(metrics_body):
    assert metrics_body["company_count"]["value"] == 10
    row = metrics_body["companies_with_industry"]
    assert row["value"] == 9
    assert row["entities_without_attr"] == 1


async def test_no_metric_reports_an_error(metrics_body):
    for name, row in metrics_body.items():
        assert "error" not in row, (name, row)


async def test_every_value_is_finite_or_none(metrics_body):
    for name, row in metrics_body.items():
        value = row["value"]
        assert value is None or math.isfinite(value), (name, value)


async def test_mrr_names_the_raw_field_that_feeds_it(metrics_body):
    assert "stripe.subscriptions._amount_monthly" in metrics_body["mrr"]["raw_fields"]


async def test_reading_metrics_writes_no_history(api, metrics_body):
    await api.get("/api/metrics")
    assert (await api.get("/api/metrics/history")).json()["history"] == []


async def test_a_snapshot_records_every_definition(api, metrics_body):
    written = (await api.post("/api/metrics/snapshots")).json()["written"]
    assert written == 9


async def test_history_shows_the_measured_estate_newest_first(api, metrics_body):
    await api.post("/api/metrics/snapshots")
    await api.post("/api/metrics/snapshots")
    rows = (await api.get("/api/metrics/history")).json()["history"]
    assert len(rows) == 18
    mrr = next(row for row in rows if row["metric"] == "mrr")
    assert mrr["value"] == 17147.0
    recorded = [row["recorded_at"] for row in rows]
    assert recorded == sorted(recorded, reverse=True)
