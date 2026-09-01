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
async def goals_body(api, session, sessionmaker_for_test):
    synced = await sync.run_all(sessionmaker_for_test, SOURCES)
    assert synced["failed"] == 0, synced
    rebuilt = await run.rebuild(session)
    assert rebuilt["ok"] is True, rebuilt
    response = await api.get("/api/insights/goals")
    assert response.status_code == 200
    return response.json()


def _row(body, goal):
    return next(row for row in body["goals"] if row["goal"] == goal)


async def test_the_estate_meets_two_misses_one_and_cannot_judge_the_trend(goals_body):
    assert goals_body["met"] == 2
    assert goals_body["missed"] == 1
    assert goals_body["unknown"] == 1


async def test_mrr_is_partway_to_its_target(goals_body):
    row = _row(goals_body, "grow_mrr")
    assert row["current"] == 17147.0
    assert row["met"] is False
    assert row["progress"] == 57.2
    assert row["entities"] == 7


async def test_won_value_has_cleared_its_target(goals_body):
    row = _row(goals_body, "grow_won_value")
    assert row["current"] == 227364.0
    assert row["met"] is True
    assert row["progress"] == 100.0
    assert row["entities"] == 8


async def test_churn_is_under_its_ceiling(goals_body):
    row = _row(goals_body, "keep_churn_low")
    assert row["current"] == 1
    assert row["met"] is True
    assert row["progress"] == 100.0
    assert row["entities"] == 1


async def test_the_trend_goal_waits_for_history(goals_body):
    row = _row(goals_body, "expand_active_subscriptions")
    assert row["met"] is None
    assert row["unknown"] == "not enough history to judge a trend"


async def test_snapshots_let_the_trend_goal_reach_a_verdict(api, goals_body):
    await api.post("/api/metrics/snapshots")
    await api.post("/api/metrics/snapshots")
    body = (await api.get("/api/insights/goals")).json()
    row = _row(body, "expand_active_subscriptions")
    assert row["met"] is False
    assert row["progress"] == 35.0
    assert row["trend"] == "up"
    assert body["met"] == 2
    assert body["missed"] == 2
    assert body["unknown"] == 0


async def test_reading_goals_writes_no_history(api, goals_body):
    await api.get("/api/insights/goals")
    await api.get("/api/insights/goals")
    assert (await api.get("/api/metrics/history")).json()["history"] == []
