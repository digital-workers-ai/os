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
async def rules_body(api, session, sessionmaker_for_test):
    synced = await sync.run_all(sessionmaker_for_test, SOURCES)
    assert synced["failed"] == 0, synced
    rebuilt = await run.rebuild(session)
    assert rebuilt["ok"] is True, rebuilt
    response = await api.get("/api/insights/rules")
    assert response.status_code == 200
    return response.json()


async def test_the_estate_produces_exactly_six_findings(rules_body):
    assert len(rules_body["findings"]) == 6
    assert rules_body["rules"] == 6


async def test_findings_split_by_severity(rules_body):
    assert rules_body["by_severity"] == {"high": 4, "medium": 1, "low": 1}


async def test_every_evaluation_was_readable(rules_body):
    assert rules_body["report"] == {"evaluated": 60, "unreadable": {}}


async def test_findings_name_the_companies_they_hang_off(rules_body):
    pairs = {(f["rule"], f["company"]) for f in rules_body["findings"]}
    assert ("subscription_past_due", "Stark Industries") in pairs
    assert ("subscription_canceled", "Umbrella Systems") in pairs


async def test_revenue_at_risk_names_the_companies_worth_saving(rules_body):
    companies = {
        f["company"] for f in rules_body["findings"] if f["rule"] == "revenue_at_risk"
    }
    assert companies == {"Wayne Enterprises", "Stark Industries"}


async def test_the_stalled_deal_is_anchored_but_unlinked(rules_body):
    finding = next(f for f in rules_body["findings"] if f["rule"] == "stalled_deal")
    assert finding["anchor"] == "hubspot|deal|hs_deal_005"
    assert finding["company"] is None


async def test_absence_is_the_evidence_for_a_missing_industry(rules_body):
    finding = next(
        f for f in rules_body["findings"] if f["rule"] == "company_without_industry"
    )
    assert finding["anchor"] == "hubspot|company|hs_company_009"
    assert finding["evidence"] == {"industry": None}


async def test_no_subscription_in_the_estate_is_new(rules_body):
    assert "new_subscription" not in {f["rule"] for f in rules_body["findings"]}


async def test_the_severity_filter_serves_exactly_the_canceled_finding(api, rules_body):
    body = (await api.get("/api/insights/rules?severity=medium")).json()
    assert [f["rule"] for f in body["findings"]] == ["subscription_canceled"]
    assert body["findings"][0]["company"] == "Umbrella Systems"
