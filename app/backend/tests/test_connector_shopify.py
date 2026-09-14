import importlib
import json
from datetime import UTC, datetime

import httpx
import pytest

from app.engine import checks, mappings, ontology, pipeline, transforms
from app.engine.report import SyncReport
from app.sources import client

FIXTURES = checks.REAL_FIXTURES.parent / "mock" / "shopify"
PULLED_AT = datetime(2026, 9, 14, tzinfo=UTC)
GATED_FIELDS = ("email", "first_name", "last_name", "phone")
GATED_ADDRESS_FIELDS = (
    "address1",
    "address2",
    "city",
    "first_name",
    "last_name",
    "name",
    "phone",
    "province",
    "province_code",
    "zip",
)


@pytest.fixture
def shopify():
    return importlib.import_module("app.sources.shopify.connector")


@pytest.fixture
def route(monkeypatch):
    def _install(handler):
        monkeypatch.setattr(client, "_transport", httpx.MockTransport(handler))

    yield _install
    monkeypatch.setattr(client, "_transport", None)


def payloads(name: str) -> list[dict]:
    return [
        row["payload"] for row in json.loads((FIXTURES / f"{name}.json").read_text())
    ]


def project(shopify, object_type: str, source_id: str, payload: dict):
    report = SyncReport()
    entities = pipeline.project_payload(
        source="shopify",
        object_type=object_type,
        source_id=source_id,
        payload=payload,
        raw_event_id=None,
        ingested_at=PULLED_AT,
        seq=1,
        onto=ontology.load(),
        line_index=mappings.by_object(mappings.load()),
        transform_map=transforms.load_map(),
        report=report,
        connector_module=shopify,
    )
    return entities, report


def a_gated_customer(customer_id: int = 9100000001) -> dict:
    return {
        "id": customer_id,
        "admin_graphql_api_id": f"gid://shopify/Customer/{customer_id}",
        "created_at": "2026-09-01T04:41:12-04:00",
        "updated_at": "2026-09-02T04:41:12-04:00",
        "currency": "CAD",
        "state": "disabled",
        "note": None,
        "orders_count": 0,
        "total_spent": "0.00",
        "last_order_id": None,
        "last_order_name": None,
        "multipass_identifier": None,
        "tags": "",
        "tax_exempt": False,
        "tax_exemptions": [],
        "verified_email": True,
        "email_marketing_consent": {
            "state": "not_subscribed",
            "opt_in_level": "single_opt_in",
            "consent_updated_at": None,
        },
        "sms_marketing_consent": {
            "state": "not_subscribed",
            "opt_in_level": "single_opt_in",
            "consent_collected_from": None,
            "consent_updated_at": None,
        },
        "addresses": [],
    }


class TestProtectedCustomerData:
    def test_the_stand_in_withholds_every_field_the_live_store_withheld(self):
        for payload in payloads("customers"):
            assert not [field for field in GATED_FIELDS if field in payload]

    def test_the_stand_in_addresses_are_country_level_only(self):
        blocks = [
            block
            for payload in payloads("customers")
            for block in [*payload["addresses"], payload.get("default_address")]
            if block is not None
        ]
        assert blocks
        for block in blocks:
            assert not [f for f in GATED_ADDRESS_FIELDS if block.get(f) is not None]
            assert block["country_name"]

    def test_a_customer_the_store_gated_carries_nothing_a_person_is_made_of(self):
        payload = a_gated_customer()
        onto = ontology.load()
        person = onto.entities["person"]
        assert not [attr for attr in person.attrs if attr in payload]

    def test_no_mapping_line_reads_a_shopify_customer(self):
        keys = [
            line.key
            for line in mappings.load()
            if line.source == "shopify" and line.object_type == "customers"
        ]
        assert keys == []

    async def test_the_pull_counts_the_customers_that_arrived_without_a_person(
        self, shopify, route
    ):
        gated = [a_gated_customer(9100000001), a_gated_customer(9100000002)]
        named = {**a_gated_customer(9100000003), "email": "jane@example.test"}

        def handler(request):
            name = request.url.path.rsplit("/", 1)[-1].removesuffix(".json")
            rows = [*gated, named] if name == "customers" else []
            return httpx.Response(200, json={name: rows})

        route(handler)
        stored = []

        async def store(session, **kwargs):
            stored.append(kwargs)

        notes = await shopify.pull(None, store)

        assert notes == {"customers_without_personal_data": 2}
        assert len(stored) == 3

    async def test_a_store_that_hands_over_its_customers_is_noted_as_nothing(
        self, shopify, route
    ):
        named = {**a_gated_customer(9100000003), "email": "jane@example.test"}

        def handler(request):
            name = request.url.path.rsplit("/", 1)[-1].removesuffix(".json")
            return httpx.Response(
                200, json={name: [named] if name == "customers" else []}
            )

        route(handler)

        async def store(session, **kwargs):
            return None

        assert await shopify.pull(None, store) is None

    async def test_a_customer_with_no_default_address_is_stored_not_raised(
        self, shopify, route
    ):
        addressless = a_gated_customer(9100000004)
        assert "default_address" not in addressless

        def handler(request):
            name = request.url.path.rsplit("/", 1)[-1].removesuffix(".json")
            rows = [addressless] if name == "customers" else []
            return httpx.Response(200, json={name: rows})

        route(handler)
        stored = []

        async def store(session, **kwargs):
            stored.append(kwargs)

        await shopify.pull(None, store)

        assert [s["source_id"] for s in stored] == ["9100000004"]
        entities, report = project(shopify, "customers", "9100000004", addressless)
        assert entities == []
        assert dict(report.skips) == {}

    def test_a_stand_in_customer_projects_nothing_at_all(self, shopify):
        for payload in payloads("customers"):
            entities, report = project(
                shopify, "customers", str(payload["id"]), payload
            )
            assert entities == []
            assert dict(report.skips) == {}
            assert dict(report.records_skipped) == {}


class TestTheCurrencyIsTheOneTheRecordCarries:
    def test_an_order_keeps_the_currency_it_arrived_with(self, shopify):
        payload = {**payloads("orders")[0], "currency": "EUR"}
        entities, _report = project(shopify, "orders", "5000000001", payload)
        assert entities[0].facts["currency"].value == "eur"

    def test_a_product_carries_no_invented_currency(self, shopify):
        entities, _report = project(
            shopify, "products", "30001", payloads("products")[0]
        )
        assert sorted(entities[0].facts) == ["category", "name", "status"]


class TestWhatTheConnectorAsksFor:
    async def test_only_orders_ask_for_every_status(self, shopify, route):
        seen: list[httpx.Request] = []

        def handler(request):
            seen.append(request)
            name = request.url.path.rsplit("/", 1)[-1].removesuffix(".json")
            return httpx.Response(200, json={name: []})

        route(handler)

        async def store(session, **kwargs):
            raise AssertionError("no records to store")

        await shopify.pull(None, store)
        asked = {
            r.url.path.rsplit("/", 1)[-1].removesuffix(".json"): dict(r.url.params)
            for r in seen
        }
        assert asked == {
            "products": {"limit": "250"},
            "orders": {"limit": "250", "status": "any"},
            "customers": {"limit": "250"},
        }

    async def test_a_full_page_is_followed_by_the_link_header_cursor(
        self, shopify, route
    ):
        seen: list[httpx.Request] = []

        def handler(request):
            seen.append(request)
            name = request.url.path.rsplit("/", 1)[-1].removesuffix(".json")
            if name != "products" or request.url.params.get("page_info"):
                return httpx.Response(200, json={name: [{"id": 2}]})
            link = (
                f"<https://mystore.myshopify.com{request.url.path}"
                f'?page_info=cursor-two&limit={shopify.PAGE_SIZE}>; rel="next"'
            )
            return httpx.Response(
                200, json={"products": [{"id": 1}]}, headers={"Link": link}
            )

        route(handler)
        stored = []

        async def store(session, **kwargs):
            stored.append(kwargs)

        await shopify.pull(None, store)

        walked = [
            dict(r.url.params) for r in seen if r.url.path.endswith("products.json")
        ]
        assert walked == [
            {"limit": "250"},
            {"limit": "250", "page_info": "cursor-two"},
        ]
        assert [s["source_id"] for s in stored if s["object_type"] == "products"] == [
            "1",
            "2",
        ]

    async def test_a_page_without_a_next_link_ends_the_walk(self, shopify, route):
        seen: list[httpx.Request] = []

        def handler(request):
            seen.append(request)
            name = request.url.path.rsplit("/", 1)[-1].removesuffix(".json")
            previous = (
                f"<https://mystore.myshopify.com{request.url.path}"
                '?page_info=cursor-one&limit=250>; rel="previous"'
            )
            return httpx.Response(
                200, json={name: [{"id": 1}]}, headers={"Link": previous}
            )

        route(handler)

        async def store(session, **kwargs):
            return None

        await shopify.pull(None, store)

        assert len(seen) == 3


class TestMoneyArrivesAsStrings:
    def test_every_mapped_money_field_is_a_string_in_the_stand_in(self):
        assert [type(p["total_price"]) for p in payloads("orders")] == [str, str]

    def test_a_decimal_string_becomes_a_number(self, shopify):
        entities, _report = project(
            shopify, "orders", "5000000001", payloads("orders")[0]
        )
        amount = entities[0].facts["amount"]
        assert amount.value_num == float(payloads("orders")[0]["total_price"])


class TestTheStandInKeepsTheLiveShape:
    def test_a_product_arrives_with_no_description_image_or_publish_date(self):
        sparse = [
            p
            for p in payloads("products")
            if p["body_html"] is None and p["published_at"] is None
        ]
        assert len(sparse) == 1
        assert sparse[0]["image"] is None
        assert sparse[0]["images"] == []

    def test_every_variant_carries_its_graphql_id_and_image_id(self):
        variants = [v for p in payloads("products") for v in p["variants"]]
        assert variants
        for variant in variants:
            assert variant["admin_graphql_api_id"]
            assert "image_id" in variant

    def test_an_untyped_product_clears_its_category_rather_than_skipping_it(
        self, shopify
    ):
        untyped = [p for p in payloads("products") if p["product_type"] == ""]
        assert len(untyped) == 1
        entities, report = project(shopify, "products", "30002", untyped[0])
        assert entities[0].facts["category"].value is None
        assert dict(report.clears) == {"category/shopify": 1}
        assert dict(report.skips) == {}

    def test_a_customer_can_arrive_with_no_address_at_all(self):
        addressless = [p for p in payloads("customers") if p["addresses"] == []]
        assert len(addressless) == 1
        assert "default_address" not in addressless[0]

    def test_a_customer_who_has_never_ordered_carries_no_last_order(self):
        customers = payloads("customers")
        never_ordered = [c for c in customers if c["last_order_id"] is None]
        ordered = [c for c in customers if c["last_order_id"] is not None]
        assert never_ordered
        assert ordered
        for customer in never_ordered:
            assert customer["last_order_name"] is None
            assert customer["orders_count"] == 0
            assert customer["total_spent"] == "0.00"
        for customer in ordered:
            assert customer["last_order_name"] is not None
            assert customer["orders_count"] > 0

    def test_an_address_company_is_a_name_on_one_customer_and_null_on_another(self):
        companies = [
            block["company"]
            for payload in payloads("customers")
            for block in payload["addresses"]
        ]
        assert None in companies
        assert [c for c in companies if isinstance(c, str)]

    def test_a_default_address_repeats_an_entry_from_addresses_company_and_all(self):
        defaulted = [
            payload
            for payload in payloads("customers")
            if payload.get("default_address") is not None
        ]
        assert len(defaulted) == 2
        for payload in defaulted:
            assert payload["default_address"] in payload["addresses"]
        companies = [p["default_address"]["company"] for p in defaulted]
        assert None in companies
        assert [c for c in companies if isinstance(c, str)]

    def test_sms_consent_is_an_object_on_every_customer(self):
        for payload in payloads("customers"):
            assert sorted(payload["sms_marketing_consent"]) == [
                "consent_collected_from",
                "consent_updated_at",
                "opt_in_level",
                "state",
            ]
