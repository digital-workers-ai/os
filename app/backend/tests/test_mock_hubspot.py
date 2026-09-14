import importlib
import sys
from pathlib import Path

import pytest
from starlette.requests import Request

from app.sources.hubspot import connector as hubspot
from tests import ground_truth

PROVIDER = Path(ground_truth.ADVERSARIAL_ROOT) / "seeds" / "providers" / "hubspot.py"
BASE = "/hubspot/crm/v3/objects"


@pytest.fixture(scope="module")
def provider():
    if not PROVIDER.is_file():
        pytest.skip("the mock providers are not mounted at /adversarial")
    if ground_truth.ADVERSARIAL_ROOT not in sys.path:
        sys.path.insert(0, ground_truth.ADVERSARIAL_ROOT)
    return importlib.import_module("seeds.providers.hubspot")


def request_for(object_type, query=b""):
    path = f"{BASE}/{object_type}"
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "raw_path": path.encode(),
            "query_string": query,
            "headers": [(b"authorization", b"Bearer mock_hs_token")],
            "scheme": "http",
            "server": ("mock", 8100),
            "root_path": "",
        }
    )


async def listing(provider, object_type, properties, *, limit=100, after=None):
    endpoint = getattr(provider, f"list_{object_type}")
    query = f"properties={properties}".encode() if properties else b""
    return await endpoint(
        request_for(object_type, query),
        limit=limit,
        after=after,
        properties=properties,
        archived=False,
    )


def properties_of(body):
    return [row["properties"] for row in body["results"]]


class TestThePropertiesParameterIsObeyed:
    async def test_only_what_was_asked_for_plus_the_always_present_three(
        self, provider
    ):
        body = await listing(provider, "companies", "domain,name")
        assert properties_of(body)
        for props in properties_of(body):
            assert set(props) == {
                "domain",
                "name",
                "createdate",
                "hs_lastmodifieddate",
                "hs_object_id",
            }

    async def test_a_property_nobody_asked_for_is_absent_however_full_the_record(
        self, provider
    ):
        body = await listing(provider, "companies", "domain")
        assert all("city" not in props for props in properties_of(body))

    async def test_asking_for_nothing_still_returns_the_always_present_three(
        self, provider
    ):
        body = await listing(provider, "contacts", None)
        for props in properties_of(body):
            assert set(props) == {"createdate", "hs_object_id", "lastmodifieddate"}

    async def test_what_the_connector_asks_for_is_what_comes_back(self, provider):
        for object_type, asked in hubspot.PROPERTIES.items():
            body = await listing(provider, object_type, ",".join(asked))
            for props in properties_of(body):
                assert set(asked) <= set(props)


class TestTheShapeMatchesTheRealApi:
    async def test_every_id_is_a_numeric_string_that_repeats_in_the_properties(
        self, provider
    ):
        body = await listing(provider, "deals", "dealname")
        for row in body["results"]:
            assert row["id"].isdigit()
            assert row["properties"]["hs_object_id"] == row["id"]

    async def test_every_record_carries_a_link_to_its_page_in_the_portal(
        self, provider
    ):
        body = await listing(provider, "contacts", "email")
        for row in body["results"]:
            assert row["url"].endswith(f"/record/0-1/{row['id']}")
            assert row["url"].startswith("https://")

    async def test_an_industry_is_the_enumeration_value_not_the_label(self, provider):
        body = await listing(provider, "companies", "industry")
        values = {props["industry"] for props in properties_of(body)}
        assert "COMPUTER_SOFTWARE" in values
        for value in values - {None}:
            assert value == value.upper().replace(" ", "_")

    async def test_a_company_hubspot_knows_only_by_domain_has_no_name(self, provider):
        body = await listing(provider, "companies", "domain,industry,name")
        blank = [p for p in properties_of(body) if p["name"] is None]
        assert len(blank) == 1
        assert blank[0]["industry"] is None
        assert blank[0]["domain"]

    async def test_an_absent_value_is_null_and_never_an_empty_string(self, provider):
        for object_type, asked in hubspot.PROPERTIES.items():
            body = await listing(provider, object_type, ",".join(asked))
            for props in properties_of(body):
                assert "" not in props.values()

    async def test_a_deal_carries_the_closed_flags_as_string_booleans(self, provider):
        body = await listing(provider, "deals", "hs_is_closed,hs_is_closed_won")
        flags = {
            (p["hs_is_closed"], p["hs_is_closed_won"]) for p in properties_of(body)
        }
        assert flags <= {("true", "true"), ("true", "false"), ("false", "false")}
        assert ("true", "true") in flags and ("false", "false") in flags

    async def test_a_deal_with_no_currency_of_its_own_says_so_with_null(self, provider):
        body = await listing(provider, "deals", "amount,deal_currency_code")
        assert properties_of(body)
        for props in properties_of(body):
            assert props["deal_currency_code"] is None


class TestPaging:
    async def test_a_short_page_hands_back_an_absolute_link_to_the_next_one(
        self, provider
    ):
        body = await listing(provider, "companies", "domain", limit=2)
        link = body["paging"]["next"]["link"]
        after = body["paging"]["next"]["after"]
        assert link == (
            f"http://mock:8100{BASE}/companies?properties=domain&after={after}"
        )

    async def test_the_cursor_is_the_last_id_on_the_page(self, provider):
        body = await listing(provider, "companies", "domain", limit=2)
        assert body["paging"]["next"]["after"] == body["results"][-1]["id"]

    async def test_the_last_page_omits_the_paging_key_entirely(self, provider):
        body = await listing(provider, "companies", "domain")
        assert "paging" not in body
