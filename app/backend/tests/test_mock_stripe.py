import importlib
import json
import sys
from pathlib import Path

import pytest
from starlette.requests import Request

from app.caches import BACKEND_DIR
from tests import ground_truth

PROVIDER = Path(ground_truth.ADVERSARIAL_ROOT) / "seeds" / "providers" / "stripe.py"
FIXTURES = BACKEND_DIR / "fixtures" / "mock" / "stripe"

STALE_TOP_LEVEL = ("current_period_start", "current_period_end", "plan")


@pytest.fixture(scope="module")
def provider():
    if not PROVIDER.is_file():
        pytest.skip("the mock providers are not mounted at /adversarial")
    if ground_truth.ADVERSARIAL_ROOT not in sys.path:
        sys.path.insert(0, ground_truth.ADVERSARIAL_ROOT)
    return importlib.import_module("seeds.providers.stripe")


def request_for(path):
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [(b"authorization", b"Bearer mock_stripe_key")],
            "scheme": "http",
            "server": ("mock", 8100),
            "root_path": "",
        }
    )


async def subscriptions(provider, status=None):
    body = await provider.list_subscriptions(
        request_for("/v1/subscriptions"),
        limit=100,
        starting_after=None,
        customer=None,
        status=status,
    )
    rows = body["data"]
    assert rows, f"the mock returned nothing for status={status!r}"
    return rows


def statuses(rows):
    return sorted({row["status"] for row in rows})


class TestTheStatusFilterAnswersLikeTheLiveApi:
    async def test_the_default_query_hides_canceled_subscriptions(self, provider):
        rows = await subscriptions(provider)
        assert "canceled" not in statuses(rows)

    async def test_the_default_query_still_returns_the_other_statuses(self, provider):
        rows = await subscriptions(provider)
        assert statuses(rows) == ["active", "past_due", "trialing"]

    async def test_status_all_returns_every_status_including_canceled(self, provider):
        rows = await subscriptions(provider, status="all")
        assert "canceled" in statuses(rows)

    async def test_status_all_is_a_wildcard_not_a_literal_match(self, provider):
        rows = await subscriptions(provider, status="all")
        assert len(rows) > len(await subscriptions(provider))

    async def test_an_explicit_status_still_narrows_to_that_status(self, provider):
        rows = await subscriptions(provider, status="canceled")
        assert statuses(rows) == ["canceled"]


class TestTheSubscriptionShapeIsTheCurrentOne:
    async def test_no_period_fields_sit_on_the_subscription(self, provider):
        rows = await subscriptions(provider, status="all")
        for row in rows:
            assert "current_period_start" not in row
            assert "current_period_end" not in row

    async def test_no_legacy_plan_sits_on_the_subscription(self, provider):
        rows = await subscriptions(provider, status="all")
        assert all("plan" not in row for row in rows)

    async def test_the_period_lives_on_the_subscription_item(self, provider):
        rows = await subscriptions(provider, status="all")
        for row in rows:
            item = row["items"]["data"][0]
            assert isinstance(item["current_period_start"], int)
            assert isinstance(item["current_period_end"], int)

    async def test_the_price_lives_on_the_subscription_item(self, provider):
        rows = await subscriptions(provider, status="all")
        for row in rows:
            assert row["items"]["data"][0]["price"]["unit_amount"] > 0


class TestTheCapturedFixturesCarryTheSameShape:
    def test_no_fixture_subscription_carries_a_stale_top_level_field(self):
        records = json.loads((FIXTURES / "subscriptions.json").read_text())
        for record in records:
            for field in STALE_TOP_LEVEL:
                assert field not in record["payload"]

    def test_every_fixture_subscription_keeps_its_item_period(self):
        records = json.loads((FIXTURES / "subscriptions.json").read_text())
        for record in records:
            item = record["payload"]["items"]["data"][0]
            assert item["current_period_start"] < item["current_period_end"]

    def test_the_canceled_fixture_is_reachable_by_the_query_we_send(self):
        records = json.loads((FIXTURES / "subscriptions.json").read_text())
        assert any(r["payload"]["status"] == "canceled" for r in records)
