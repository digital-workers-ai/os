import gzip
import importlib
import io
import json
import pkgutil
import zipfile

import httpx
import pytest

from app import clock, sync
from app.engine import mappings
from app.sources import catalog, client, creds, registry, util
from app.sources.hubspot import connector as hubspot
from app.sources.stripe import connector as stripe

ALL_SOURCES = {
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
    "meta",
    "google_ads",
    "google_analytics",
    "activecampaign",
    "zoom",
    "segment",
    "amplitude",
    "mixpanel",
    "smartlook",
    "snapchat",
    "twitter",
    "pinterest",
    "linkedin",
    "meta_ad_library",
    "google_ads_transparency",
    "serp",
    "ai_answers",
    "competitor_pages",
    "linkedin_posts",
}


def connector(name):
    return importlib.import_module(f"app.sources.{name}.connector")


def zipped_ndjson(text: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        bundle.writestr(
            "12345/12345_2026-09-04_0#0.json.gz", gzip.compress(text.encode())
        )
    return buffer.getvalue()


EXPORT_BODIES = [
    ("amplitude", lambda text: {"content": zipped_ndjson(text)}),
    ("mixpanel", lambda text: {"text": text}),
]


@pytest.fixture
def pull(monkeypatch):
    def _run(module, body, *, text=None, content=None):
        stored = []

        def handler(request):
            if content is not None:
                return httpx.Response(200, content=content)
            if text is not None:
                return httpx.Response(200, text=text)
            return httpx.Response(200, json=body)

        monkeypatch.setattr(client, "_transport", httpx.MockTransport(handler))

        async def fake_store(session, **kwargs):
            stored.append(kwargs)

        async def _go():
            notes = await module.pull(None, fake_store)
            return notes, stored

        return _go()

    yield _run
    monkeypatch.setattr(client, "_transport", None)


class TestWhatTheConnectorActuallyAsksFor:
    @pytest.fixture
    def capture(self, monkeypatch):
        seen = []

        def _install(body):
            def handler(request):
                seen.append(request)
                return httpx.Response(200, json=body)

            monkeypatch.setattr(client, "_transport", httpx.MockTransport(handler))
            return seen

        yield _install
        monkeypatch.setattr(client, "_transport", None)

    async def test_hubspot_asks_for_the_properties_its_mappings_read(self, capture):
        seen = capture({"results": [], "paging": {}})

        async def store(session, **kwargs):
            pass

        await hubspot.pull(None, store)

        asked = {r.url.path: r.url.params.get("properties") for r in seen}
        for path, properties in asked.items():
            assert properties, f"{path} requested no properties"
        companies = next(v for k, v in asked.items() if k.endswith("companies"))
        assert "industry" in companies
        assert "domain" in companies and "name" in companies

    async def test_hubspot_asks_the_closed_flags_not_the_stage_id(self, capture):
        seen = capture({"results": [], "paging": {}})

        async def store(session, **kwargs):
            pass

        await hubspot.pull(None, store)

        asked = {r.url.path: r.url.params.get("properties") for r in seen}
        deals = next(v for k, v in asked.items() if k.endswith("deals"))
        assert "hs_is_closed_won" in deals and "hs_is_closed" in deals
        assert "deal_currency_code" in deals
        assert "dealstage" not in deals

    async def test_hubspot_reads_full_pages_so_the_page_cap_is_far_away(self, capture):
        seen = capture({"results": [], "paging": {}})

        async def store(session, **kwargs):
            pass

        await hubspot.pull(None, store)

        assert {r.url.params.get("limit") for r in seen} == {"100"}

    async def test_hubspot_follows_the_cursor_until_the_paging_key_is_gone(
        self, monkeypatch
    ):
        seen = []

        def handler(request):
            seen.append(request)
            if request.url.params.get("after"):
                return httpx.Response(200, json={"results": [{"id": "2"}]})
            return httpx.Response(
                200,
                json={
                    "results": [{"id": "1"}],
                    "paging": {"next": {"after": "1", "link": "https://x/y?after=1"}},
                },
            )

        monkeypatch.setattr(client, "_transport", httpx.MockTransport(handler))
        stored = []

        async def store(session, **kwargs):
            stored.append(kwargs["source_id"])

        await hubspot.pull(None, store)
        monkeypatch.setattr(client, "_transport", None)

        assert len(seen) == 6
        assert stored.count("1") == 3 and stored.count("2") == 3

    async def test_hubspot_declares_no_account_wide_currency(self):
        assert not hasattr(hubspot, "ACCOUNT_CURRENCY")

    async def test_stripe_walks_customers_then_subscriptions(self, capture):
        seen = capture({"data": [{"id": "x_1"}], "has_more": False})
        stored = []

        async def store(session, **kwargs):
            stored.append(kwargs)

        notes = await stripe.pull(None, store)

        assert notes is None
        paths = {r.url.path for r in seen}
        assert {p.rsplit("/", 1)[-1] for p in paths} == {"customers", "subscriptions"}
        assert {(s["source"], s["object_type"]) for s in stored} == {
            ("stripe", "customers"),
            ("stripe", "subscriptions"),
        }

    async def test_stripe_asks_for_subscriptions_of_every_status(self, capture):
        seen = capture({"data": [], "has_more": False})

        async def store(session, **kwargs):
            pass

        await stripe.pull(None, store)

        asked = {r.url.path: r.url.params.get("status") for r in seen}
        assert asked["/v1/subscriptions"] == "all"

    async def test_stripe_sends_no_status_where_the_endpoint_has_none(self, capture):
        seen = capture({"data": [], "has_more": False})

        async def store(session, **kwargs):
            pass

        await stripe.pull(None, store)

        asked = {r.url.path: r.url.params.get("status") for r in seen}
        assert asked["/v1/customers"] is None

    async def test_stripe_pins_the_api_version_its_shapes_were_read_from(self, capture):
        seen = capture({"data": [], "has_more": False})

        async def store(session, **kwargs):
            pass

        await stripe.pull(None, store)

        assert seen
        assert {r.headers.get("stripe-version") for r in seen} == {stripe.API_VERSION}

    async def test_the_pinned_stripe_version_is_the_one_the_docs_record(self):
        assert stripe.API_VERSION == "2025-03-31.basil"

    async def test_stripe_observes_customers_by_the_only_timestamp_stripe_has(self):
        assert stripe.OBSERVED_AT == {
            "customers": "created",
            "subscriptions": "created",
        }

    async def test_zendesk_walks_its_three_collections_with_a_page_size(self, capture):
        seen = capture({"tickets": [{"id": 1001}]})
        stored = []

        async def store(session, **kwargs):
            stored.append(kwargs)

        notes = await connector("zendesk").pull(None, store)

        assert notes is None
        assert {r.url.path for r in seen} == {
            "/tickets.json",
            "/users.json",
            "/organizations.json",
        }
        assert all(r.url.params.get("page[size]") == "6" for r in seen)
        assert {(s["object_type"], s["source_id"]) for s in stored} == {
            ("tickets", "1001"),
            ("users", "1001"),
            ("organizations", "1001"),
        }

    async def test_intercom_reads_each_endpoints_own_collection_key(self, capture):
        seen = capture(
            {
                "data": [{"id": "c1"}],
                "conversations": [{"id": "v1"}],
                "pages": {},
            }
        )
        stored = []

        async def store(session, **kwargs):
            stored.append(kwargs)

        notes = await connector("intercom").pull(None, store)

        assert notes is None
        assert {r.url.path for r in seen} == {"/contacts", "/conversations"}
        assert all(r.url.params.get("per_page") == "150" for r in seen)
        assert {(s["object_type"], s["source_id"]) for s in stored} == {
            ("contacts", "c1"),
            ("conversations", "v1"),
        }

    async def test_klaviyo_walks_profiles_then_flows(self, capture):
        seen = capture({"data": [{"id": "p1"}], "links": {}})
        stored = []

        async def store(session, **kwargs):
            stored.append(kwargs)

        notes = await connector("klaviyo").pull(None, store)

        assert notes is None
        assert {r.url.path: r.url.params.get("page[size]") for r in seen} == {
            "/api/profiles": "100",
            "/api/flows": "50",
        }
        assert {(s["object_type"], s["source_id"]) for s in stored} == {
            ("profiles", "p1"),
            ("flows", "p1"),
        }

    async def test_calendly_keys_events_by_the_last_uri_segment(self, capture):
        seen = capture(
            {
                "collection": [
                    {"uri": "https://api.calendly.com/scheduled_events/evt_1"}
                ],
                "pagination": {},
            }
        )
        stored = []

        async def store(session, **kwargs):
            stored.append(kwargs)

        notes = await connector("calendly").pull(None, store)

        assert notes is None
        assert [r.url.path for r in seen] == [
            "/users/me",
            "/scheduled_events",
            "/scheduled_events/evt_1/invitees",
        ]
        assert seen[1].url.params.get("count") == "100"
        assert [(s["object_type"], s["source_id"]) for s in stored] == [
            ("scheduled_events", "evt_1")
        ]

    async def test_sendgrid_walks_singlesends_then_contacts(self, capture):
        seen = capture({"result": [{"id": "s1"}]})
        stored = []

        async def store(session, **kwargs):
            stored.append(kwargs)

        notes = await connector("sendgrid").pull(None, store)

        assert notes is None
        assert {r.url.path for r in seen} == {
            "/v3/marketing/singlesends",
            "/v3/marketing/contacts",
        }
        assert {(s["object_type"], s["source_id"]) for s in stored} == {
            ("singlesends", "s1"),
            ("contacts", "s1"),
        }

    async def test_customerio_walks_campaigns_segments_then_activities(self, capture):
        seen = capture(
            {
                "campaigns": [{"id": 7}],
                "segments": [{"id": 8}],
                "activities": [{"delivery_id": "d1"}],
            }
        )
        stored = []

        async def store(session, **kwargs):
            stored.append(kwargs)

        notes = await connector("customerio").pull(None, store)

        assert notes is None
        asked = {r.url.path: r.url.params.get("limit") for r in seen}
        assert asked == {
            "/v1/campaigns": "5",
            "/v1/segments": "5",
            "/v1/activities": "100",
        }
        assert ("activities", "d1") in {
            (s["object_type"], s["source_id"]) for s in stored
        }


class TestPickId:
    def test_a_non_mapping_has_no_id(self):
        assert util.pick_id("not a dict", "id") is None

    @pytest.mark.parametrize("record", [{}, {"id": None}, {"id": ""}, {"id": "   "}])
    def test_an_absent_or_blank_id_is_none_never_a_placeholder(self, record):
        assert util.pick_id(record, "id") is None

    def test_the_first_field_that_carries_a_value_wins(self):
        assert util.pick_id({"uuid": "u1"}, "id", "uuid") == "u1"


class TestWindow:
    def test_ninety_days_end_on_the_pinned_clock(self):
        assert util.window(90) == ("2026-06-07", "2026-09-04")

    def test_a_single_day_window_is_today_alone(self):
        assert util.window(1) == ("2026-09-04", "2026-09-04")

    def test_the_default_is_ninety_days(self):
        assert util.window() == util.window(90)

    async def test_store_all_counts_the_records_it_could_not_key(self):
        stored = []

        async def fake_store(session, **kwargs):
            stored.append(kwargs)

        notes = await util.store_all(
            None, fake_store, [{"id": "a"}, {}], source="x", object_type="y"
        )
        assert len(stored) == 1
        assert notes == {"missing_id": 1}

    async def test_store_all_id_of_overrides_the_field_lookup(self):
        stored = []

        async def fake_store(session, **kwargs):
            stored.append(kwargs)

        notes = await util.store_all(
            None,
            fake_store,
            [{"uri": "https://api.calendly.com/scheduled_events/e1"}],
            source="x",
            object_type="y",
            id_of=lambda r: (r.get("uri") or "").rsplit("/", 1)[-1] or None,
        )
        assert [s["source_id"] for s in stored] == ["e1"]
        assert notes == {}

    async def test_store_all_counts_a_none_from_id_of_as_missing(self):
        stored = []

        async def fake_store(session, **kwargs):
            stored.append(kwargs)

        notes = await util.store_all(
            None,
            fake_store,
            [{"id": "would_have_been_stored"}],
            source="x",
            object_type="y",
            id_of=lambda r: None,
        )
        assert stored == []
        assert notes == {"missing_id": 1}


class TestBatchOneShapes:
    async def test_calendly_counts_an_event_with_no_uri(self, pull):
        notes, stored = await pull(
            connector("calendly"),
            {
                "collection": [
                    {"uri": "https://api.calendly.com/scheduled_events/e1"},
                    {},
                ],
                "pagination": {},
            },
        )
        assert [s["source_id"] for s in stored] == ["e1"]
        assert notes == {"missing_id": 1}

    async def test_sendgrid_reads_either_result_or_results(self, pull):
        _notes, stored = await pull(connector("sendgrid"), {"results": [{"id": "s1"}]})
        assert [s["source_id"] for s in stored] == ["s1", "s1"]

    async def test_sendgrid_stores_an_unlisted_body_whole(self, pull):
        _notes, stored = await pull(connector("sendgrid"), {"unexpected": "shape"})
        assert {s["source_id"] for s in stored} == {"singlesends", "contacts"}
        assert all(s["raw_payload"] == {"unexpected": "shape"} for s in stored)


class TestCredentials:
    def test_an_unknown_source_names_itself(self):
        with pytest.raises(KeyError, match="nope"):
            creds.credentials_for("nope")


class TestRegistry:
    def test_every_connector_module_is_discovered(self):
        assert len(ALL_SOURCES) == 33
        assert set(registry.discover()) == ALL_SOURCES

    def test_discovery_is_cached(self):
        assert registry.discover() is registry.discover()

    def test_a_module_with_no_source_is_refused(self, monkeypatch):
        self._reject(
            monkeypatch, "defines no SOURCE", type("M", (), {"pull": lambda *a: None})
        )

    def test_a_module_with_no_pull_is_refused(self, monkeypatch):
        self._reject(monkeypatch, "no callable pull", type("M", (), {"SOURCE": "x"}))

    def test_two_modules_claiming_one_source_are_refused(self, monkeypatch):
        module = type("M", (), {"SOURCE": "dupe", "pull": lambda *a: None})
        self._reject(monkeypatch, "duplicate SOURCE", module, count=2)

    @staticmethod
    def _reject(monkeypatch, message, module, count=1):
        monkeypatch.setattr(registry, "_cache", None)
        monkeypatch.setattr(
            pkgutil,
            "iter_modules",
            lambda path: [
                type("I", (), {"name": f"fake{n}", "ispkg": True})()
                for n in range(count)
            ],
        )
        monkeypatch.setattr(registry.importlib, "import_module", lambda name: module)
        with pytest.raises(registry.ConnectorRegistrationError, match=message):
            registry.discover()
        monkeypatch.setattr(registry, "_cache", None)


class TestGoogleSheets:
    async def test_a_sheet_with_only_a_header_row_stores_nothing(self, pull):
        notes, stored = await pull(
            connector("google_sheets"), {"values": [["Name", "Amount"]]}
        )
        assert notes is None and stored == []

    async def test_an_empty_sheet_stores_nothing(self, pull):
        notes, stored = await pull(connector("google_sheets"), {"values": []})
        assert notes is None and stored == []

    async def test_a_row_longer_than_its_header_is_counted_and_kept(self, pull):
        notes, stored = await pull(
            connector("google_sheets"),
            {"values": [["Name", "Amount"], ["Acme", "100", "surprise"]]},
        )
        assert notes == {"ragged_rows": 1}
        assert stored[0]["raw_payload"]["_extra_2"] == "surprise"

    async def test_a_row_with_an_empty_key_column_is_keyed_by_content(self, pull):
        _notes, stored = await pull(
            connector("google_sheets"), {"values": [["Name", "Amount"], ["", "100"]]}
        )
        assert len(stored[0]["source_id"]) == 32

    async def test_a_short_row_pads_rather_than_misaligning(self, pull):
        _notes, stored = await pull(
            connector("google_sheets"), {"values": [["Name", "Amount"], ["Acme"]]}
        )
        assert stored[0]["raw_payload"] == {"Name": "Acme", "Amount": None}


class TestWooCommerceBodyShapes:
    async def test_a_bare_list_is_the_records(self, pull):
        _notes, stored = await pull(connector("woocommerce"), [{"id": 1}])
        assert {(s["object_type"], s["source_id"]) for s in stored} == {
            ("products", "1"),
            ("orders", "1"),
            ("customers", "1"),
        }

    async def test_a_dict_body_yields_each_endpoints_own_key(self, pull):
        _notes, stored = await pull(
            connector("woocommerce"),
            {
                "products": [{"id": 11}],
                "orders": [{"id": 22}],
                "customers": [{"id": 33}],
            },
        )
        assert {(s["object_type"], s["source_id"]) for s in stored} == {
            ("products", "11"),
            ("orders", "22"),
            ("customers", "33"),
        }

    async def test_any_other_shape_is_no_records(self, pull):
        notes, stored = await pull(connector("woocommerce"), "not a collection")
        assert notes is None and stored == []


class TestASingleRequestPullAdmitsWhatItCannotKnow:
    @pytest.fixture
    def rows(self, monkeypatch):
        def _install(body):
            def handler(request):
                return httpx.Response(200, json=body)

            monkeypatch.setattr(client, "_transport", httpx.MockTransport(handler))

        yield _install
        monkeypatch.setattr(client, "_transport", None)

    async def _pull(self, module, rows, body):
        rows(body)

        async def store(session, **kwargs):
            pass

        with client.collect_stats() as stats:
            await module.pull(None, store)
        return stats

    async def test_woocommerce_reports_a_full_page_as_possibly_incomplete(self, rows):
        stats = await self._pull(
            connector("woocommerce"), rows, [{"id": n} for n in range(100)]
        )
        assert stats.truncated is True
        assert any("full page" in r for r in stats.truncation_reasons)

    async def test_woocommerce_short_pages_are_complete(self, rows):
        stats = await self._pull(connector("woocommerce"), rows, [{"id": 1}])
        assert stats.truncated is False

    async def test_snapchat_reports_a_full_page_as_possibly_incomplete(self, rows):
        stats = await self._pull(
            connector("snapchat"),
            rows,
            {"organizations": [{"id": f"o{n}"} for n in range(100)]},
        )
        assert stats.truncated is True
        assert any("page" in r for r in stats.truncation_reasons)

    async def test_snapchat_short_pages_are_complete(self, rows):
        stats = await self._pull(
            connector("snapchat"), rows, {"organizations": [{"id": "o1"}]}
        )
        assert stats.truncated is False


class TestBasicAuthCredentials:
    @pytest.mark.parametrize(
        "source,auth",
        [
            ("mailchimp", ("anystring", "mock_mailchimp_key")),
            ("twilio", ("mock_account_sid", "mock_auth_token")),
            ("woocommerce", ("mock_consumer_key", "mock_consumer_secret")),
            ("mixpanel", ("mock_mixpanel_secret", "")),
            ("amplitude", ("mock_amplitude_key", "mock_amplitude_secret")),
        ],
    )
    def test_the_basic_auth_pair_is_declared(self, source, auth):
        assert creds.credentials_for(source).auth == auth

    @pytest.mark.parametrize("source", ["hubspot", "stripe", "salesforce", "shopify"])
    def test_bearer_sources_declare_no_auth_pair(self, source):
        assert creds.credentials_for(source).auth is None


class TestWhatTheBatchTwoConnectorsAskFor:
    @pytest.fixture
    def capture(self, monkeypatch):
        seen = []

        def _install(body):
            def handler(request):
                seen.append(request)
                return httpx.Response(200, json=body)

            monkeypatch.setattr(client, "_transport", httpx.MockTransport(handler))
            return seen

        yield _install
        monkeypatch.setattr(client, "_transport", None)

    async def test_shopify_walks_its_three_json_endpoints(self, capture):
        seen = capture(
            {
                "products": [{"id": 1}],
                "orders": [{"id": 2}],
                "customers": [{"id": 3}],
            }
        )
        stored = []

        async def store(session, **kwargs):
            stored.append(kwargs)

        notes = await connector("shopify").pull(None, store)

        assert notes == {"customers_without_personal_data": 1}
        assert {r.url.path for r in seen} == {
            "/admin/api/2024-01/products.json",
            "/admin/api/2024-01/orders.json",
            "/admin/api/2024-01/customers.json",
        }
        assert all(r.url.params.get("limit") == "250" for r in seen)
        assert {(s["object_type"], s["source_id"]) for s in stored} == {
            ("products", "1"),
            ("orders", "2"),
            ("customers", "3"),
        }

    async def test_mailchimp_walks_lists_then_campaigns_by_offset(self, capture):
        seen = capture(
            {
                "lists": [{"id": "l1"}],
                "campaigns": [{"id": "c1"}],
                "total_items": 1,
            }
        )
        stored = []

        async def store(session, **kwargs):
            stored.append(kwargs)

        notes = await connector("mailchimp").pull(None, store)

        assert notes is None
        assert {r.url.path for r in seen} == {"/3.0/lists", "/3.0/campaigns"}
        assert all(r.url.params.get("count") == "1000" for r in seen)
        assert all(r.url.params.get("offset") == "0" for r in seen)
        assert {(s["object_type"], s["source_id"]) for s in stored} == {
            ("lists", "l1"),
            ("campaigns", "c1"),
        }

    async def test_twilio_asks_its_account_messages_with_basic_auth(self, capture):
        seen = capture({"messages": [{"sid": "SM1"}]})
        stored = []

        async def store(session, **kwargs):
            stored.append(kwargs)

        notes = await connector("twilio").pull(None, store)

        assert notes is None
        assert [r.url.path for r in seen] == [
            "/2010-04-01/Accounts/mock_account_sid/Messages.json"
        ]
        assert seen[0].url.params.get("PageSize") == "1"
        assert seen[0].headers.get("Authorization", "").startswith("Basic ")
        assert [(s["object_type"], s["source_id"]) for s in stored] == [
            ("messages", "SM1")
        ]

    async def test_google_sheets_asks_for_the_pipeline_range(self, capture):
        seen = capture({"values": [["Company"], ["Acme"]]})
        stored = []

        async def store(session, **kwargs):
            stored.append(kwargs)

        await connector("google_sheets").pull(None, store)

        assert len(seen) == 1
        assert "/spreadsheets/" in seen[0].url.path
        assert seen[0].url.path.endswith("/values/Pipeline!A1:F20")
        assert [(s["object_type"], s["source_id"]) for s in stored] == [
            ("rows", "Acme")
        ]

    async def test_woocommerce_issues_one_capped_request_per_endpoint(self, capture):
        seen = capture([{"id": 1}])

        async def store(session, **kwargs):
            pass

        notes = await connector("woocommerce").pull(None, store)

        assert notes is None
        assert {r.url.path.rsplit("/", 1)[-1] for r in seen} == {
            "products",
            "orders",
            "customers",
        }
        assert len(seen) == 3
        assert all(r.url.params.get("per_page") == "100" for r in seen)


class TestBatchThreeShapes:
    async def test_google_ads_counts_a_row_with_no_campaign_id(self, pull):
        notes, stored = await pull(
            connector("google_ads"),
            [
                {
                    "results": [
                        {"campaign": {"id": "c1"}},
                        {"campaign": {}},
                        {"metrics": {}},
                    ]
                }
            ],
        )
        assert [(s["object_type"], s["source_id"]) for s in stored] == [
            ("campaigns", "c1")
        ]
        assert notes == {"missing_id": 5}

    async def test_meta_counts_an_insight_row_with_no_id(self, pull):
        notes, stored = await pull(connector("meta"), {"data": [{"no_id": True}]})
        assert stored == []
        assert notes["missing_id"] >= 1

    async def test_google_ads_reads_a_bare_dict_body(self, pull):
        _notes, stored = await pull(
            connector("google_ads"), {"results": [{"campaign": {"id": "c9"}}]}
        )
        assert [s["source_id"] for s in stored] == ["c9"]

    @pytest.mark.parametrize("body", [[], "not a collection"])
    async def test_google_ads_stores_nothing_from_an_alien_body(self, pull, body):
        notes, stored = await pull(connector("google_ads"), body)
        assert notes is None and stored == []


class TestGoogleAnalyticsPull:
    @pytest.fixture
    def report_pages(self, monkeypatch):
        seen = []

        def _install(pages):
            def handler(request):
                body = json.loads(request.content)
                seen.append(body)
                return httpx.Response(200, json=pages[body["offset"]])

            monkeypatch.setattr(client, "_transport", httpx.MockTransport(handler))
            return seen

        yield _install
        monkeypatch.setattr(client, "_transport", None)

    @staticmethod
    def _row(day, channel):
        return {
            "dimensionValues": [{"value": day}, {"value": channel}],
            "metricValues": [{"value": "1"}, {"value": "2"}, {"value": "3"}],
        }

    async def test_the_offset_walk_stops_at_the_row_count(self, report_pages):
        seen = report_pages(
            {
                0: {
                    "rows": [self._row("20260701", c) for c in ("a", "b", "c")],
                    "rowCount": 5,
                },
                3: {
                    "rows": [self._row("20260701", c) for c in ("d", "e")],
                    "rowCount": 5,
                },
            }
        )
        stored = []

        async def store(session, **kwargs):
            stored.append(kwargs)

        notes = await connector("google_analytics").pull(None, store)

        assert notes is None
        assert [b["offset"] for b in seen] == [0, 3]
        assert len(stored) == 5
        assert all(len(s["source_id"]) == 32 for s in stored)
        assert all(s["object_type"] == "report_rows" for s in stored)
        assert len({s["source_id"] for s in stored}) == 5

    async def test_an_empty_page_with_no_row_count_ends_the_walk(self, report_pages):
        seen = report_pages({0: {"rows": []}})
        stored = []

        async def store(session, **kwargs):
            stored.append(kwargs)

        await connector("google_analytics").pull(None, store)

        assert len(seen) == 1
        assert stored == []


class TestWhatTheBatchThreeConnectorsAskFor:
    @pytest.fixture
    def capture(self, monkeypatch):
        seen = []

        def _install(handler_or_body):
            def handler(request):
                seen.append(request)
                if callable(handler_or_body):
                    return httpx.Response(200, json=handler_or_body(request))
                return httpx.Response(200, json=handler_or_body)

            monkeypatch.setattr(client, "_transport", httpx.MockTransport(handler))
            return seen

        yield _install
        monkeypatch.setattr(client, "_transport", None)

    async def test_meta_asks_for_campaign_level_insights(self, capture):
        seen = capture({"data": [], "paging": {}})

        async def store(session, **kwargs):
            pass

        await connector("meta").pull(None, store)

        insights = [r for r in seen if r.url.path.endswith("/insights")]
        assert insights, "no insights request was issued"
        assert all(r.url.params.get("level") == "campaign" for r in insights)

    async def test_segment_walks_the_cursor_envelope_to_the_end(self, capture):
        def body(request):
            if request.url.params.get("pagination.cursor") == "cur2":
                return {
                    "data": {
                        "sources": [{"name": "workspace-two"}],
                        "pagination": {},
                    }
                }
            return {
                "data": {
                    "sources": [{"id": "src_1", "name": "one"}],
                    "pagination": {"next": "cur2"},
                }
            }

        seen = capture(body)
        stored = []

        async def store(session, **kwargs):
            stored.append(kwargs)

        notes = await connector("segment").pull(None, store)

        assert notes is None
        assert [r.url.path for r in seen] == ["/sources", "/sources"]
        assert all(r.url.params.get("pagination.count") == "1" for r in seen)
        assert seen[1].url.params.get("pagination.cursor") == "cur2"
        assert [(s["object_type"], s["source_id"]) for s in stored] == [
            ("sources", "src_1"),
            ("sources", "workspace-two"),
        ]

    async def test_activecampaign_walks_contacts_then_campaigns_with_its_token(
        self, capture
    ):
        seen = capture({"contacts": [{"id": "10"}], "campaigns": [{"id": "20"}]})
        stored = []

        async def store(session, **kwargs):
            stored.append(kwargs)

        notes = await connector("activecampaign").pull(None, store)

        assert notes is None
        assert {r.url.path for r in seen} == {
            "/api/3/contacts",
            "/api/3/campaigns",
        }
        assert all(r.url.params.get("limit") == "100" for r in seen)
        assert all(r.headers.get("Api-Token") == "mock_ac_token" for r in seen)
        assert {(s["object_type"], s["source_id"]) for s in stored} == {
            ("contacts", "10"),
            ("campaigns", "20"),
        }


class TestWhatTheNinetyDayConnectorsAskFor:
    @pytest.fixture
    def capture(self, monkeypatch):
        seen = []

        def _install(handler_or_body):
            def handler(request):
                seen.append(request)
                if callable(handler_or_body):
                    return httpx.Response(200, json=handler_or_body(request))
                return httpx.Response(200, json=handler_or_body)

            monkeypatch.setattr(client, "_transport", httpx.MockTransport(handler))
            return seen

        yield _install
        monkeypatch.setattr(client, "_transport", None)

    @pytest.fixture
    def stored(self):
        return []

    @pytest.fixture
    def store(self, stored):
        async def _store(session, **kwargs):
            stored.append(kwargs)

        return _store

    @staticmethod
    def _meta_body(request):
        path = request.url.path
        if path.endswith("/me/accounts"):
            return {
                "data": [
                    {"id": "page_001", "instagram_business_account": {"id": "ig_001"}}
                ]
            }
        if path.endswith("/insights") and request.url.params.get("time_increment"):
            return {
                "data": [
                    {"campaign_id": "ad3", "date_start": "2026-09-01", "spend": "1.00"}
                ]
            }
        if path.endswith("/posts"):
            return {"data": [{"id": "page_001_20260901", "message": "hello"}]}
        if path.endswith("/media"):
            return {"data": [{"id": "media_20260901", "caption": "hi"}]}
        return {"data": [], "paging": {}}

    @staticmethod
    def _google_ads_body(request):
        if "BETWEEN" in json.loads(request.content)["query"]:
            return [
                {
                    "results": [
                        {
                            "campaign": {"id": "ad1"},
                            "segments": {"date": "2026-09-01"},
                            "metrics": {"costMicros": "1000000"},
                        }
                    ]
                }
            ]
        return [{"results": []}]

    async def test_google_analytics_asks_for_the_ninety_days_ending_on_the_clock(
        self, capture, store
    ):
        seen = capture({"rows": []})

        await connector("google_analytics").pull(None, store)

        body = json.loads(seen[0].content)
        assert body["dateRanges"] == [
            {"startDate": "2026-06-07", "endDate": "2026-09-04"}
        ]

    async def test_google_analytics_reads_pages_of_a_hundred(self, capture, store):
        seen = capture({"rows": []})

        await connector("google_analytics").pull(None, store)

        assert json.loads(seen[0].content)["limit"] == 100

    async def test_meta_asks_every_account_for_daily_insights_over_the_window(
        self, capture, store
    ):
        seen = capture(self._meta_body)

        await connector("meta").pull(None, store)

        daily = [
            r
            for r in seen
            if r.url.path.endswith("/insights")
            and r.url.params.get("time_increment") == "1"
        ]
        assert len(daily) == len(creds._MOCK_VALUES["meta"]["account_ids"])
        assert all(r.url.params.get("level") == "campaign" for r in daily)
        assert all(
            r.url.params.get("time_range")
            == json.dumps({"since": "2026-06-07", "until": "2026-09-04"})
            for r in daily
        )

    async def test_meta_stores_a_daily_insight_under_its_campaign_and_day(
        self, capture, store, stored
    ):
        capture(self._meta_body)

        await connector("meta").pull(None, store)

        assert ("daily_insights", "ad3|2026-09-01") in {
            (s["object_type"], s["source_id"]) for s in stored
        }

    async def test_meta_asks_each_page_for_its_posts_over_the_window(
        self, capture, store
    ):
        seen = capture(self._meta_body)

        await connector("meta").pull(None, store)

        posts = [r for r in seen if r.url.path == "/v25.0/page_001/posts"]
        assert len(posts) == 1
        assert posts[0].url.params.get("since") == "2026-06-07"
        assert posts[0].url.params.get("until") == "2026-09-04"
        assert posts[0].url.params.get("fields") == (
            "id,message,created_time,type,shares,likes.summary(true),"
            "comments.summary(true)"
        )

    async def test_meta_stores_a_page_post_under_its_own_id(
        self, capture, store, stored
    ):
        capture(self._meta_body)

        await connector("meta").pull(None, store)

        assert ("page_posts", "page_001_20260901") in {
            (s["object_type"], s["source_id"]) for s in stored
        }

    async def test_meta_asks_each_instagram_account_for_its_media_over_the_window(
        self, capture, store
    ):
        seen = capture(self._meta_body)

        await connector("meta").pull(None, store)

        media = [r for r in seen if r.url.path == "/v25.0/ig_001/media"]
        assert len(media) == 1
        assert media[0].url.params.get("since") == "2026-06-07"
        assert media[0].url.params.get("until") == "2026-09-04"
        assert media[0].url.params.get("fields") == (
            "id,caption,timestamp,media_type,permalink,like_count,comments_count"
        )

    async def test_meta_stores_an_instagram_media_item_under_its_own_id(
        self, capture, store, stored
    ):
        capture(self._meta_body)

        await connector("meta").pull(None, store)

        assert ("ig_media", "media_20260901") in {
            (s["object_type"], s["source_id"]) for s in stored
        }

    async def test_meta_asks_no_media_of_a_page_with_no_instagram_account(
        self, capture, store
    ):
        def body(request):
            if request.url.path.endswith("/me/accounts"):
                return {"data": [{"id": "page_002"}]}
            return self._meta_body(request)

        seen = capture(body)

        await connector("meta").pull(None, store)

        assert [r.url.path for r in seen if r.url.path.endswith("/media")] == []
        assert [r.url.path for r in seen if r.url.path.endswith("/posts")] == [
            "/v25.0/page_002/posts"
        ]

    async def test_google_ads_asks_for_one_row_per_campaign_day_over_the_window(
        self, capture, store
    ):
        seen = capture(self._google_ads_body)

        await connector("google_ads").pull(None, store)

        daily = [
            q
            for q in (json.loads(r.content)["query"] for r in seen)
            if "segments.date BETWEEN '2026-06-07' AND '2026-09-04'" in q
        ]
        assert len(daily) == 1
        assert daily[0].startswith(
            "SELECT campaign.id, segments.date, metrics.costMicros, metrics.clicks, "
            "metrics.impressions, metrics.conversions, metrics.conversionsValue "
            "FROM campaign"
        )

    async def test_google_ads_stores_a_daily_row_under_its_campaign_and_day(
        self, capture, store, stored
    ):
        capture(self._google_ads_body)

        await connector("google_ads").pull(None, store)

        assert ("daily_campaigns", "ad1|2026-09-01") in {
            (s["object_type"], s["source_id"]) for s in stored
        }


class TestSheetRowsSharingACompanyAreACountedCollision:
    async def test_two_rows_with_one_company_collide_in_the_sync_receipt(
        self, session, sessionmaker_for_test, monkeypatch
    ):
        def handler(request):
            return httpx.Response(
                200,
                json={
                    "values": [
                        ["Company", "Amount"],
                        ["Acme", "100"],
                        ["Acme", "200"],
                    ]
                },
            )

        monkeypatch.setattr(client, "_transport", httpx.MockTransport(handler))
        result = await sync.run_all(sessionmaker_for_test, ["google_sheets"])
        monkeypatch.setattr(client, "_transport", None)

        assert result["results"][0]["rows_colliding"] == 1
        detail = result["results"][0]["detail"] or ""
        assert "rows/Acme" in detail and "collision" in detail.lower()


class TestExportStreams:
    @pytest.mark.parametrize(
        "name,body", EXPORT_BODIES, ids=[n for n, _ in EXPORT_BODIES]
    )
    async def test_a_blank_line_is_skipped_silently(self, pull, name, body):
        notes, stored = await pull(
            connector(name), None, **body('{"a":1}\n\n   \n{"a":2}')
        )
        assert len(stored) == 2
        assert notes is None

    @pytest.mark.parametrize(
        "name,body", EXPORT_BODIES, ids=[n for n, _ in EXPORT_BODIES]
    )
    async def test_a_malformed_line_is_counted_not_fatal(self, pull, name, body):
        notes, stored = await pull(
            connector(name), None, **body('{"a":1}\nnot json at all\n{"a":2}')
        )
        assert len(stored) == 2
        assert notes == {"malformed_lines": 1}

    @pytest.mark.parametrize(
        "name,body", EXPORT_BODIES, ids=[n for n, _ in EXPORT_BODIES]
    )
    async def test_a_line_with_no_vendor_id_is_keyed_by_its_content(
        self, pull, name, body
    ):
        _notes, stored = await pull(connector(name), None, **body('{"no_id_here":1}'))
        assert len(stored[0]["source_id"]) == 32
        assert stored[0]["object_type"] == "events"

    async def test_amplitude_reads_the_zipped_archive_the_export_returns(self, pull):
        _notes, stored = await pull(
            connector("amplitude"),
            None,
            content=zipped_ndjson('{"$insert_id":"a"}\n{"$insert_id":"b"}'),
        )
        assert [s["source_id"] for s in stored] == ["a", "b"]

    async def test_a_plain_text_body_is_not_silently_read_as_zero_events(self, pull):
        with pytest.raises(client.ConnectorError):
            await pull(connector("amplitude"), None, text='{"$insert_id":"a"}')

    async def test_amplitude_prefers_the_vendor_insert_id(self, pull):
        _notes, stored = await pull(
            connector("amplitude"),
            None,
            content=zipped_ndjson('{"$insert_id":"abc","uuid":"z"}'),
        )
        assert stored[0]["source_id"] == "abc"

    async def test_amplitude_reads_no_undollared_insert_id(self, pull):
        _notes, stored = await pull(
            connector("amplitude"),
            None,
            content=zipped_ndjson('{"insert_id":"abc","uuid":"z"}'),
        )
        assert stored[0]["source_id"] == "z"

    async def test_amplitude_falls_back_to_the_uuid(self, pull):
        _notes, stored = await pull(
            connector("amplitude"), None, content=zipped_ndjson('{"uuid":"z"}')
        )
        assert stored[0]["source_id"] == "z"

    async def test_amplitude_asks_for_a_rolling_window(self, monkeypatch):
        seen = []

        def handler(request):
            seen.append(request)
            return httpx.Response(200, content=zipped_ndjson(""))

        monkeypatch.setattr(client, "_transport", httpx.MockTransport(handler))

        async def store(session, **kwargs):
            pass

        await connector("amplitude").pull(None, store)
        monkeypatch.setattr(client, "_transport", None)

        since, until = util.window()
        assert seen[0].url.params["start"] == f"{since.replace('-', '')}T00"
        assert seen[0].url.params["end"] == f"{until.replace('-', '')}T23"

    async def test_the_amplitude_window_is_hours_not_iso_dates(self, monkeypatch):
        seen = []

        def handler(request):
            seen.append(request)
            return httpx.Response(200, content=zipped_ndjson(""))

        monkeypatch.setattr(client, "_transport", httpx.MockTransport(handler))

        async def store(session, **kwargs):
            pass

        await connector("amplitude").pull(None, store)
        monkeypatch.setattr(client, "_transport", None)

        assert seen[0].url.params["start"] == "20260607T00"
        assert seen[0].url.params["end"] == "20260904T23"

    async def test_amplitude_observes_events_by_the_export_timestamp(self):
        assert connector("amplitude").OBSERVED_AT == {"events": "event_time"}

    async def test_mixpanel_reads_its_id_out_of_properties(self, pull):
        _notes, stored = await pull(
            connector("mixpanel"), None, text='{"properties":{"$insert_id":"mp-1"}}'
        )
        assert stored[0]["source_id"] == "mp-1"


class TestBatchFourShapes:
    async def test_snapchat_counts_an_org_with_no_id(self, pull):
        notes, stored = await pull(
            connector("snapchat"),
            {"organizations": [{"organization": {"id": "o1"}}, {"organization": {}}]},
        )
        assert [s["source_id"] for s in stored] == ["o1"]
        assert notes == {"missing_id": 1}

    async def test_snapchat_refuses_a_body_that_is_not_a_list(self, pull):
        notes, stored = await pull(
            connector("snapchat"), {"organizations": {"id": "o1"}}
        )
        assert notes is None and stored == []

    async def test_twitter_refuses_a_body_that_is_not_a_list(self, pull):
        notes, stored = await pull(connector("twitter"), {"data": {"id": "a1"}})
        assert notes is None and stored == []

    async def test_smartlook_accepts_a_bare_list(self, pull):
        _notes, stored = await pull(connector("smartlook"), [{"id": "e1"}])
        assert [(s["object_type"], s["source_id"]) for s in stored] == [
            ("events", "e1")
        ]

    async def test_smartlook_treats_an_unusable_shape_as_no_events(self, pull):
        notes, stored = await pull(connector("smartlook"), {"data": "not a list"})
        assert stored == [] and notes is None

    async def test_smartlook_treats_a_scalar_body_as_no_events(self, pull):
        notes, stored = await pull(connector("smartlook"), "not a collection")
        assert stored == [] and notes is None

    async def test_twitter_stores_the_tweets_it_is_given(self, pull):
        notes, stored = await pull(connector("twitter"), {"data": [{"id": "a1"}]})
        assert notes is None
        assert [(s["object_type"], s["source_id"]) for s in stored] == [
            ("tweets", "a1")
        ]


class TestWhatTheBatchFourConnectorsAskFor:
    @pytest.fixture
    def capture(self, monkeypatch):
        seen = []

        def _install(handler_or_body):
            def handler(request):
                seen.append(request)
                if callable(handler_or_body):
                    return httpx.Response(200, json=handler_or_body(request))
                return httpx.Response(200, json=handler_or_body)

            monkeypatch.setattr(client, "_transport", httpx.MockTransport(handler))
            return seen

        yield _install
        monkeypatch.setattr(client, "_transport", None)

    async def test_pinterest_walks_the_bookmark_to_its_end(self, capture):
        def body(request):
            if request.url.params.get("bookmark") == "b2":
                return {"items": [{"id": "aa2"}], "bookmark": None}
            return {"items": [{"id": "aa1"}], "bookmark": "b2"}

        seen = capture(body)
        stored = []

        async def store(session, **kwargs):
            stored.append(kwargs)

        notes = await connector("pinterest").pull(None, store)

        assert notes is None
        accounts = [r for r in seen if r.url.path == "/ad_accounts"]
        assert len(accounts) == 2
        assert all(r.url.params.get("page_size") == "1" for r in accounts)
        assert accounts[1].url.params.get("bookmark") == "b2"
        assert [
            (s["object_type"], s["source_id"])
            for s in stored
            if s["object_type"] == "ad_accounts"
        ] == [("ad_accounts", "aa1"), ("ad_accounts", "aa2")]

    async def test_linkedin_walks_the_page_token_with_its_three_headers(self, capture):
        def body(request):
            if request.url.params.get("pageToken") == "t1":
                return {"elements": [{"id": 102}], "metadata": {}}
            return {"elements": [{"id": 101}], "metadata": {"nextPageToken": "t1"}}

        seen = capture(body)
        stored = []

        async def store(session, **kwargs):
            stored.append(kwargs)

        await connector("linkedin").pull(None, store)

        accounts = [r for r in seen if r.url.path == "/adAccounts"]
        assert len(accounts) == 2
        assert all(r.url.params.get("q") == "search" for r in accounts)
        assert all(r.url.params.get("pageSize") == "1" for r in accounts)
        assert accounts[1].url.params.get("pageToken") == "t1"
        for request in seen:
            assert request.headers.get("Authorization") == "Bearer mock_linkedin_token"
            assert request.headers.get("linkedin-version") == "202401"
            assert request.headers.get("x-restli-protocol-version") == "2.0.0"
        assert [
            (s["object_type"], s["source_id"])
            for s in stored
            if s["object_type"] == "ad_accounts"
        ] == [("ad_accounts", "101"), ("ad_accounts", "102")]


class TestCatalog:
    def test_an_unlabelled_source_falls_back_rather_than_crashing(self):
        row = catalog.entry("never_registered")
        assert row["category"] == "Other"
        assert row["label"] == "never_registered"
        assert row["unlocks"] == ""

    def test_a_connector_with_no_catalog_entry_is_a_build_error(self, monkeypatch):
        monkeypatch.setattr(catalog, "_META", dict(list(catalog._META.items())[:5]))
        with pytest.raises(RuntimeError, match="missing metadata"):
            catalog.catalog()

    def test_the_catalog_names_all_sources_in_order(self):
        rows = catalog.catalog()
        assert [r["source"] for r in rows] == sorted(ALL_SOURCES)
        for row in rows:
            assert row["label"] and row["category"] and row["unlocks"]


class _SocialCapture:
    @pytest.fixture
    def capture(self, monkeypatch):
        seen = []

        def _install(handler_or_body):
            def handler(request):
                seen.append(request)
                if callable(handler_or_body):
                    return httpx.Response(200, json=handler_or_body(request))
                return httpx.Response(200, json=handler_or_body)

            monkeypatch.setattr(client, "_transport", httpx.MockTransport(handler))
            return seen

        yield _install
        monkeypatch.setattr(client, "_transport", None)

    @pytest.fixture
    def stored(self):
        return []

    @pytest.fixture
    def store(self, stored):
        async def _store(session, **kwargs):
            stored.append(kwargs)

        return _store


PAGE_METRICS = (
    "page_impressions_unique,page_impressions,page_post_engagements,"
    "page_fan_adds,page_fan_removes,page_views_total"
)
IG_METRICS = "reach,impressions,accounts_engaged,follower_count,profile_views"
POST_METRICS = "post_impressions_unique,post_impressions,post_clicks"
MEDIA_METRICS = "reach,impressions,views,saved"


def _series(names, points):
    return {"data": [{"name": name, "values": points} for name in names]}


class TestWhatMetaAsksForItsPagesAndPosts(_SocialCapture):
    @staticmethod
    def _body(request):
        path = request.url.path
        params = request.url.params
        if path.endswith("/me/accounts"):
            return {
                "data": [
                    {"id": "page_001", "instagram_business_account": {"id": "ig_001"}}
                ]
            }
        if path.endswith("/posts"):
            return {"data": [{"id": "page_001_20260901", "message": "hello"}]}
        if path.endswith("/media"):
            return {"data": [{"id": "media_20260901", "caption": "hi"}]}
        if path == "/v25.0/page_001/insights":
            return _series(
                PAGE_METRICS.split(","),
                [
                    {"value": 10, "end_time": "2026-09-01T07:00:00+0000"},
                    {"value": 12, "end_time": "2026-09-02T07:00:00+0000"},
                ],
            )
        if path == "/v25.0/ig_001/insights":
            return _series(
                IG_METRICS.split(","),
                [{"value": 7, "end_time": "2026-09-01T07:00:00+0000"}],
            )
        if path == "/v25.0/page_001_20260901/insights":
            return _series(POST_METRICS.split(","), [{"value": 5}])
        if path == "/v25.0/media_20260901/insights":
            return _series(MEDIA_METRICS.split(","), [{"value": 4}])
        if path.endswith("/insights") and params.get("time_increment"):
            return {"data": []}
        return {"data": [], "paging": {}}

    def _keys(self, stored):
        return {(s["object_type"], s["source_id"]) for s in stored}

    async def test_meta_asks_each_page_for_its_daily_insights_over_the_window(
        self, capture, store
    ):
        seen = capture(self._body)

        await connector("meta").pull(None, store)

        daily = [r for r in seen if r.url.path == "/v25.0/page_001/insights"]
        assert len(daily) == 1
        assert daily[0].url.params.get("metric") == PAGE_METRICS
        assert daily[0].url.params.get("period") == "day"
        assert daily[0].url.params.get("since") == "2026-06-07"
        assert daily[0].url.params.get("until") == "2026-09-04"

    async def test_meta_stores_one_page_row_per_day_under_its_page_and_day(
        self, capture, store, stored
    ):
        capture(self._body)

        await connector("meta").pull(None, store)

        rows = {
            s["source_id"]: s["raw_payload"]
            for s in stored
            if s["object_type"] == "page_insights"
        }
        assert set(rows) == {"page_001|2026-09-01", "page_001|2026-09-02"}
        assert rows["page_001|2026-09-01"] == {
            "node": "page_001",
            "date": "2026-09-01",
            "values": dict.fromkeys(PAGE_METRICS.split(","), 10),
        }

    async def test_meta_asks_each_instagram_account_for_its_daily_insights(
        self, capture, store
    ):
        seen = capture(self._body)

        await connector("meta").pull(None, store)

        daily = [r for r in seen if r.url.path == "/v25.0/ig_001/insights"]
        assert len(daily) == 1
        assert daily[0].url.params.get("metric") == IG_METRICS
        assert daily[0].url.params.get("period") == "day"
        assert daily[0].url.params.get("since") == "2026-06-07"
        assert daily[0].url.params.get("until") == "2026-09-04"

    async def test_meta_stores_an_instagram_day_under_its_account_and_day(
        self, capture, store, stored
    ):
        capture(self._body)

        await connector("meta").pull(None, store)

        assert ("ig_insights", "ig_001|2026-09-01") in self._keys(stored)

    async def test_meta_asks_each_post_for_its_lifetime_insights(self, capture, store):
        seen = capture(self._body)

        await connector("meta").pull(None, store)

        per_post = [
            r for r in seen if r.url.path == "/v25.0/page_001_20260901/insights"
        ]
        assert len(per_post) == 1
        assert per_post[0].url.params.get("metric") == POST_METRICS

    async def test_meta_stores_post_insights_under_the_post_id_so_they_merge(
        self, capture, store, stored
    ):
        capture(self._body)

        await connector("meta").pull(None, store)

        rows = {
            s["source_id"]: s["raw_payload"]
            for s in stored
            if s["object_type"] == "post_insights"
        }
        assert rows == {
            "page_001_20260901": {
                "id": "page_001_20260901",
                "values": dict.fromkeys(POST_METRICS.split(","), 5),
            }
        }

    async def test_meta_asks_each_media_item_for_its_lifetime_insights(
        self, capture, store
    ):
        seen = capture(self._body)

        await connector("meta").pull(None, store)

        per_media = [r for r in seen if r.url.path == "/v25.0/media_20260901/insights"]
        assert len(per_media) == 1
        assert per_media[0].url.params.get("metric") == MEDIA_METRICS

    async def test_meta_stores_media_insights_under_the_media_id_so_they_merge(
        self, capture, store, stored
    ):
        capture(self._body)

        await connector("meta").pull(None, store)

        rows = {
            s["source_id"]: s["raw_payload"]
            for s in stored
            if s["object_type"] == "media_insights"
        }
        assert rows == {
            "media_20260901": {
                "id": "media_20260901",
                "values": dict.fromkeys(MEDIA_METRICS.split(","), 4),
            }
        }

    async def test_meta_drops_a_daily_point_with_no_end_time(
        self, capture, store, stored
    ):
        def body(request):
            if request.url.path == "/v25.0/page_001/insights":
                return _series(["page_impressions"], [{"value": 10}])
            return self._body(request)

        capture(body)

        await connector("meta").pull(None, store)

        assert [s for s in stored if s["object_type"] == "page_insights"] == []

    async def test_meta_drops_a_lifetime_series_with_no_points(
        self, capture, store, stored
    ):
        def body(request):
            if request.url.path == "/v25.0/media_20260901/insights":
                return {"data": [{"name": "reach", "values": []}, {"values": [{}]}]}
            return self._body(request)

        capture(body)

        await connector("meta").pull(None, store)

        rows = [s for s in stored if s["object_type"] == "media_insights"]
        assert rows[0]["raw_payload"] == {"id": "media_20260901", "values": {}}

    async def test_meta_asks_no_insights_of_a_post_with_no_id(
        self, capture, store, stored
    ):
        def body(request):
            if request.url.path.endswith("/posts"):
                return {"data": [{"message": "unkeyed"}]}
            return self._body(request)

        seen = capture(body)

        notes = await connector("meta").pull(None, store)

        assert [s for s in stored if s["object_type"] == "post_insights"] == []
        assert notes == {"missing_id": 1}
        assert "/v25.0/None/insights" not in {r.url.path for r in seen}


ORGANIZATION = "urn:li:organization:1"
INTERVALS = (
    "(timeRange:(start:1780790400000,end:1788566400000),timeGranularityType:DAY)"
)


class TestWhatLinkedinAsksForItsOrganization(_SocialCapture):
    @staticmethod
    def _body(request):
        path = request.url.path
        if path == "/posts":
            return {
                "elements": [
                    {
                        "id": "urn:li:share:1",
                        "commentary": "hello",
                        "publishedAt": 1788271200000,
                    }
                ],
                "paging": {"start": 0, "count": 100, "total": 1},
            }
        if path == "/organizationalEntityShareStatistics":
            return {
                "elements": [
                    {
                        "share": "urn:li:share:1",
                        "totalShareStatistics": {"impressionCount": 100},
                    }
                ]
            }
        if path in (
            "/organizationalEntityFollowerStatistics",
            "/organizationPageStatistics",
        ):
            return {
                "elements": [
                    {"timeRange": {"start": 1788220800000, "end": 1788307200000}}
                ]
            }
        return {"elements": [], "metadata": {}}

    def _keys(self, stored):
        return {(s["object_type"], s["source_id"]) for s in stored}

    async def test_linkedin_asks_its_organization_for_posts(self, capture, store):
        seen = capture(self._body)

        await connector("linkedin").pull(None, store)

        posts = [r for r in seen if r.url.path == "/posts"]
        assert len(posts) == 1
        assert posts[0].url.params.get("author") == ORGANIZATION
        assert posts[0].url.params.get("q") == "author"
        assert posts[0].url.params.get("start") == "0"
        assert posts[0].url.params.get("count") == "100"
        assert posts[0].headers["linkedin-version"] == "202401"

    async def test_linkedin_stores_a_post_under_its_urn(self, capture, store, stored):
        capture(self._body)

        await connector("linkedin").pull(None, store)

        assert ("posts", "urn:li:share:1") in self._keys(stored)

    async def test_linkedin_asks_share_statistics_for_the_posts_it_found(
        self, capture, store
    ):
        seen = capture(self._body)

        await connector("linkedin").pull(None, store)

        stats = [
            r for r in seen if r.url.path == "/organizationalEntityShareStatistics"
        ]
        assert len(stats) == 1
        assert stats[0].url.params.get("q") == "organizationalEntity"
        assert stats[0].url.params.get("organizationalEntity") == ORGANIZATION
        assert stats[0].url.params.get("shares") == "List(urn:li:share:1)"

    async def test_linkedin_asks_no_share_statistics_when_there_are_no_posts(
        self, capture, store
    ):
        def body(request):
            if request.url.path == "/posts":
                return {
                    "elements": [],
                    "paging": {"start": 0, "count": 100, "total": 0},
                }
            return self._body(request)

        seen = capture(body)

        await connector("linkedin").pull(None, store)

        assert "/organizationalEntityShareStatistics" not in {r.url.path for r in seen}

    async def test_linkedin_stores_share_statistics_under_the_post_urn_so_they_merge(
        self, capture, store, stored
    ):
        capture(self._body)

        await connector("linkedin").pull(None, store)

        assert ("post_stats", "urn:li:share:1") in self._keys(stored)

    async def test_linkedin_asks_follower_statistics_by_day_over_the_window(
        self, capture, store
    ):
        seen = capture(self._body)

        await connector("linkedin").pull(None, store)

        rows = [
            r for r in seen if r.url.path == "/organizationalEntityFollowerStatistics"
        ]
        assert len(rows) == 1
        assert rows[0].url.params.get("q") == "organizationalEntity"
        assert rows[0].url.params.get("organizationalEntity") == ORGANIZATION
        assert rows[0].url.params.get("timeIntervals") == INTERVALS

    async def test_linkedin_stores_a_follower_day_under_its_organization_and_day(
        self, capture, store, stored
    ):
        capture(self._body)

        await connector("linkedin").pull(None, store)

        assert ("follower_stats", f"{ORGANIZATION}|2026-09-01") in self._keys(stored)

    async def test_linkedin_asks_page_statistics_by_day_over_the_window(
        self, capture, store
    ):
        seen = capture(self._body)

        await connector("linkedin").pull(None, store)

        rows = [r for r in seen if r.url.path == "/organizationPageStatistics"]
        assert len(rows) == 1
        assert rows[0].url.params.get("q") == "organization"
        assert rows[0].url.params.get("organization") == ORGANIZATION
        assert rows[0].url.params.get("timeIntervals") == INTERVALS

    async def test_linkedin_stores_a_page_day_under_the_same_organization_and_day(
        self, capture, store, stored
    ):
        capture(self._body)

        await connector("linkedin").pull(None, store)

        assert ("page_stats", f"{ORGANIZATION}|2026-09-01") in self._keys(stored)

    async def test_linkedin_counts_a_day_row_with_no_time_range_as_missing(
        self, capture, store, stored
    ):
        def body(request):
            if request.url.path == "/organizationPageStatistics":
                return {"elements": [{"totalPageStatistics": {}}, {"timeRange": {}}]}
            return self._body(request)

        capture(body)

        notes = await connector("linkedin").pull(None, store)

        assert [s for s in stored if s["object_type"] == "page_stats"] == []
        assert notes == {"missing_id": 2}


TWITTER_USER = "4030300010"
TWITTER_TWEETS = f"/2/users/{TWITTER_USER}/tweets"


class TestWhatTwitterAsksForItsTweets(_SocialCapture):
    @pytest.fixture(autouse=True)
    def configured_user(self, monkeypatch):
        monkeypatch.setitem(creds._MOCK_VALUES, "twitter", {"user_id": TWITTER_USER})

    @staticmethod
    def _tweet(tweet_id):
        return {
            "id": tweet_id,
            "text": "hello",
            "created_at": "2026-09-01T14:00:00.000Z",
            "public_metrics": {"impression_count": 100},
        }

    def _body(self, request):
        if request.url.path == TWITTER_TWEETS:
            return {"data": [self._tweet("1")], "meta": {"result_count": 1}}
        return {"data": []}

    async def test_twitter_asks_its_user_for_tweets_over_the_window(
        self, capture, store
    ):
        seen = capture(self._body)

        await connector("twitter").pull(None, store)

        tweets = [r for r in seen if r.url.path == TWITTER_TWEETS]
        assert len(tweets) == 1
        assert tweets[0].url.params.get("start_time") == "2026-06-07T00:00:00Z"
        assert tweets[0].url.params.get("end_time") == "2026-09-04T23:59:59Z"
        assert tweets[0].url.params.get("max_results") == "100"
        assert tweets[0].url.params.get("tweet.fields") == "created_at,public_metrics"
        assert tweets[0].headers["authorization"] == "Bearer mock_twitter_token"

    async def test_twitter_asks_for_nothing_but_those_tweets(self, capture, store):
        seen = capture(self._body)

        await connector("twitter").pull(None, store)

        assert [r.url.path for r in seen] == [TWITTER_TWEETS]

    async def test_twitter_stores_a_tweet_under_its_own_id(
        self, capture, store, stored
    ):
        capture(self._body)

        await connector("twitter").pull(None, store)

        assert ("tweets", "1") in {(s["object_type"], s["source_id"]) for s in stored}

    async def test_twitter_walks_the_next_token_to_its_end(
        self, capture, store, stored
    ):
        def body(request):
            if request.url.path != TWITTER_TWEETS:
                return {"data": []}
            if request.url.params.get("pagination_token") == "tok":
                return {"data": [self._tweet("2")], "meta": {"result_count": 1}}
            return {
                "data": [self._tweet("1")],
                "meta": {"result_count": 1, "next_token": "tok"},
            }

        seen = capture(body)

        await connector("twitter").pull(None, store)

        pages = [r for r in seen if r.url.path == TWITTER_TWEETS]
        assert [r.url.params.get("pagination_token") for r in pages] == [None, "tok"]
        assert {s["source_id"] for s in stored if s["object_type"] == "tweets"} == {
            "1",
            "2",
        }

    async def test_twitter_treats_a_tweet_body_with_no_data_as_no_tweets(
        self, capture, store, stored
    ):
        def body(request):
            if request.url.path == TWITTER_TWEETS:
                return {"meta": {"result_count": 0}}
            return {"data": []}

        capture(body)

        notes = await connector("twitter").pull(None, store)

        assert [s for s in stored if s["object_type"] == "tweets"] == []
        assert notes is None


class TestWhatPinterestAsksForItsPinsAndAccount(_SocialCapture):
    @staticmethod
    def _body(request):
        path = request.url.path
        if path == "/pins":
            return {
                "items": [
                    {
                        "id": "pin_1",
                        "title": "hello",
                        "created_at": "2026-09-01T14:00:00",
                        "media": {"media_type": "image"},
                        "pin_metrics": {"all_time": {"IMPRESSION": 100}},
                    }
                ],
                "bookmark": None,
            }
        if path == "/user_account/analytics":
            return {
                "all": {
                    "daily_metrics": [
                        {
                            "date": "2026-09-01",
                            "data_status": "READY",
                            "metrics": {"IMPRESSION": 10, "ENGAGEMENT": 3},
                        }
                    ],
                    "summary_metrics": {"IMPRESSION": 10},
                }
            }
        return {"items": [], "bookmark": None}

    def _keys(self, stored):
        return {(s["object_type"], s["source_id"]) for s in stored}

    async def test_pinterest_asks_for_its_pins_with_their_metrics(self, capture, store):
        seen = capture(self._body)

        await connector("pinterest").pull(None, store)

        pins = [r for r in seen if r.url.path == "/pins"]
        assert len(pins) == 1
        assert pins[0].url.params.get("pin_metrics") == "true"
        assert pins[0].url.params.get("page_size") == "100"
        assert pins[0].headers["authorization"] == "Bearer mock_pinterest_token"

    async def test_pinterest_stores_a_pin_under_its_own_id(
        self, capture, store, stored
    ):
        capture(self._body)

        await connector("pinterest").pull(None, store)

        assert ("pins", "pin_1") in self._keys(stored)

    async def test_pinterest_asks_its_account_for_daily_analytics_over_the_window(
        self, capture, store
    ):
        seen = capture(self._body)

        await connector("pinterest").pull(None, store)

        rows = [r for r in seen if r.url.path == "/user_account/analytics"]
        assert len(rows) == 1
        assert rows[0].url.params.get("start_date") == "2026-06-07"
        assert rows[0].url.params.get("end_date") == "2026-09-04"
        assert rows[0].url.params.get("metric_types") == (
            "IMPRESSION,ENGAGEMENT,TOTAL_AUDIENCE,PIN_CLICK,SAVE"
        )

    async def test_pinterest_stores_an_account_day_under_the_account_and_day(
        self, capture, store, stored
    ):
        capture(self._body)

        await connector("pinterest").pull(None, store)

        rows = {
            s["source_id"]: s["raw_payload"]
            for s in stored
            if s["object_type"] == "account_analytics"
        }
        assert set(rows) == {"user_account|2026-09-01"}
        assert rows["user_account|2026-09-01"]["metrics"] == {
            "IMPRESSION": 10,
            "ENGAGEMENT": 3,
        }

    async def test_pinterest_counts_an_account_day_with_no_date_as_missing(
        self, capture, store, stored
    ):
        def body(request):
            if request.url.path == "/user_account/analytics":
                return {"all": {"daily_metrics": [{"metrics": {"IMPRESSION": 1}}]}}
            return self._body(request)

        capture(body)

        notes = await connector("pinterest").pull(None, store)

        assert [s for s in stored if s["object_type"] == "account_analytics"] == []
        assert notes == {"missing_id": 1}

    async def test_pinterest_treats_an_analytics_body_of_the_wrong_shape_as_no_days(
        self, capture, store, stored
    ):
        def body(request):
            if request.url.path == "/user_account/analytics":
                return [1, 2]
            return self._body(request)

        capture(body)

        notes = await connector("pinterest").pull(None, store)

        assert [s for s in stored if s["object_type"] == "account_analytics"] == []
        assert notes is None


class TestCompetitorConnectors(_SocialCapture):
    @staticmethod
    def _competitors():
        from app.engine import competitors

        return competitors.tracked()

    def _page_ids(self):
        return {str(spec["meta_page_id"]) for spec in self._competitors().values()}

    def _advertiser_ids(self):
        return {
            str(spec["google_advertiser_id"]) for spec in self._competitors().values()
        }

    @staticmethod
    def _meta_body(request):
        path = request.url.path
        if path == "/v25.0/ads_archive":
            page_id = request.url.params.get("search_page_ids")
            return {
                "data": [
                    {
                        "id": f"ad_{page_id}",
                        "page_id": page_id,
                        "ad_creative_bodies": ["Stop scrolling"],
                        "ad_delivery_start_time": "2026-06-15",
                        "ad_snapshot_url": "https://facebook.test/ads/1",
                    }
                ],
                "paging": {},
            }
        page_id = path.rsplit("/", 1)[-1]
        return {
            "id": page_id,
            "name": f"Page {page_id}",
            "website": f"https://{page_id}.test",
        }

    @staticmethod
    def _creative(advertiser_id, n, **extra):
        creative_id = f"CR{advertiser_id}_{n}"
        return {
            "advertiser_id": advertiser_id,
            "advertiser": f"Advertiser {advertiser_id}",
            "ad_creative_id": creative_id,
            "format": "text",
            "width": 300,
            "height": 250,
            "target_domain": f"{advertiser_id.lower()}.test",
            "first_shown": 1781515800,
            "last_shown": 1788271200,
            "total_days_shown": 78,
            "details_link": (
                "https://adstransparency.google.com/advertiser/"
                f"{advertiser_id}/creative/{creative_id}"
            ),
            "serpapi_details_link": (
                "https://serpapi.com/search.json?engine="
                "google_ads_transparency_center_details"
                f"&advertiser_id={advertiser_id}&creative_id={creative_id}"
            ),
            **extra,
        }

    def _file_domains(self):
        return {
            str(spec["google_advertiser_id"]): str(spec["domain"])
            for spec in self._competitors().values()
        }

    def _google_body(self, request):
        advertiser_id = request.url.params.get("advertiser_id")
        return {
            "ad_creatives": [
                self._creative(advertiser_id, 1),
                self._creative(advertiser_id, 2),
            ],
            "serpapi_pagination": {},
        }

    def _keys(self, stored):
        return {(s["object_type"], s["source_id"]) for s in stored}

    async def test_meta_ad_library_asks_each_competitor_page_for_its_website(
        self, capture, store
    ):
        seen = capture(self._meta_body)

        await connector("meta_ad_library").pull(None, store)

        pages = [r for r in seen if r.url.path != "/v25.0/ads_archive"]
        assert {r.url.path for r in pages} == {
            f"/v25.0/{page_id}" for page_id in self._page_ids()
        }
        for request in pages:
            fields = set(request.url.params.get("fields", "").split(","))
            assert {"id", "name", "website"} <= fields
            assert request.url.params.get("access_token")

    async def test_meta_ad_library_asks_the_archive_for_each_pages_ads(
        self, capture, store
    ):
        seen = capture(self._meta_body)

        await connector("meta_ad_library").pull(None, store)

        archive = [r for r in seen if r.url.path == "/v25.0/ads_archive"]
        assert len(archive) == len(self._page_ids())
        assert {r.url.params.get("search_page_ids") for r in archive} == (
            self._page_ids()
        )
        for request in archive:
            params = request.url.params
            assert params.get("ad_active_status") == "ALL"
            assert params.get("ad_reached_countries")
            assert params.get("access_token")
            assert {
                "ad_creative_bodies",
                "ad_delivery_start_time",
                "ad_delivery_stop_time",
                "ad_snapshot_url",
                "page_id",
            } <= set(params.get("fields", "").split(","))

    async def test_meta_ad_library_stores_each_page_and_its_ads_as_they_arrived(
        self, capture, store, stored
    ):
        capture(self._meta_body)

        notes = await connector("meta_ad_library").pull(None, store)

        assert notes is None
        assert {s["source"] for s in stored} == {"meta_ad_library"}
        page_ids = self._page_ids()
        assert self._keys(stored) == {("pages", p) for p in page_ids} | {
            ("ads", f"ad_{p}") for p in page_ids
        }
        ads = {
            s["source_id"]: s["raw_payload"]
            for s in stored
            if s["object_type"] == "ads"
        }
        pages = {
            s["source_id"]: s["raw_payload"]
            for s in stored
            if s["object_type"] == "pages"
        }
        for page_id in page_ids:
            assert pages[page_id]["website"] == f"https://{page_id}.test"
            assert ads[f"ad_{page_id}"]["ad_creative_bodies"] == ["Stop scrolling"]

    async def test_google_ads_transparency_asks_the_center_for_each_advertiser(
        self, capture, store
    ):
        seen = capture(self._google_body)

        await connector("google_ads_transparency").pull(None, store)

        assert {r.url.path for r in seen} == {"/search"}
        assert len(seen) == len(self._advertiser_ids())
        assert {r.url.params.get("advertiser_id") for r in seen} == (
            self._advertiser_ids()
        )
        for request in seen:
            assert request.url.params.get("engine") == "google_ads_transparency_center"
            assert request.url.params.get("api_key")

    async def test_google_ads_transparency_stores_each_creative_under_its_creative_id(
        self, capture, store, stored
    ):
        capture(self._google_body)

        notes = await connector("google_ads_transparency").pull(None, store)

        assert notes is None
        assert {s["source"] for s in stored} == {"google_ads_transparency"}
        creatives = {
            s["source_id"]: s["raw_payload"]
            for s in stored
            if s["object_type"] == "creatives"
        }
        assert set(creatives) == {
            f"CR{advertiser_id}_{n}"
            for advertiser_id in self._advertiser_ids()
            for n in (1, 2)
        }
        for advertiser_id in self._advertiser_ids():
            assert creatives[f"CR{advertiser_id}_1"] == self._creative(advertiser_id, 1)

    async def test_google_ads_transparency_builds_one_advertiser_from_its_creatives(
        self, capture, store, stored
    ):
        capture(self._google_body)

        await connector("google_ads_transparency").pull(None, store)

        advertisers = [s for s in stored if s["object_type"] == "advertisers"]
        assert sorted(s["source_id"] for s in advertisers) == sorted(
            self._advertiser_ids()
        )
        for row in advertisers:
            advertiser_id = row["source_id"]
            assert row["raw_payload"] == {
                "id": advertiser_id,
                "name": f"Advertiser {advertiser_id}",
                "domain": f"{advertiser_id.lower()}.test",
            }

    async def test_the_advertisers_domain_comes_from_the_first_creative_that_has_one(
        self, capture, store, stored
    ):
        def body(request):
            advertiser_id = request.url.params.get("advertiser_id")
            first = self._creative(advertiser_id, 1)
            first.pop("target_domain")
            return {
                "ad_creatives": [first, self._creative(advertiser_id, 2)],
                "serpapi_pagination": {},
            }

        capture(body)

        await connector("google_ads_transparency").pull(None, store)

        for row in [s for s in stored if s["object_type"] == "advertisers"]:
            advertiser_id = row["source_id"]
            assert row["raw_payload"]["domain"] == f"{advertiser_id.lower()}.test"
            assert row["raw_payload"]["name"] == f"Advertiser {advertiser_id}"

    async def test_an_advertiser_whose_creatives_name_no_domain_takes_the_files(
        self, capture, store, stored
    ):
        def body(request):
            advertiser_id = request.url.params.get("advertiser_id")
            creatives = [self._creative(advertiser_id, n) for n in (1, 2)]
            for creative in creatives:
                creative.pop("target_domain")
            return {"ad_creatives": creatives, "serpapi_pagination": {}}

        capture(body)

        await connector("google_ads_transparency").pull(None, store)

        domains = self._file_domains()
        for row in [s for s in stored if s["object_type"] == "advertisers"]:
            assert row["raw_payload"]["domain"] == domains[row["source_id"]]

    def test_google_creatives_are_read_by_their_details_link_and_never_named(self):
        labels = {
            line.key: line.label
            for line in mappings.load()
            if line.source == "google_ads_transparency"
            and line.object_type == "creatives"
        }
        assert labels["google_ads_transparency.creatives.details_link"] == "url"
        assert "name" not in labels.values()
        assert not [key for key in labels if key.endswith(".link")]

    async def test_google_ads_transparency_walks_the_page_token_to_its_end(
        self, capture, store, stored
    ):
        def body(request):
            advertiser_id = request.url.params.get("advertiser_id")
            if request.url.params.get("next_page_token") == "tok":
                return {
                    "ad_creatives": [self._creative(advertiser_id, 2)],
                    "serpapi_pagination": {},
                }
            return {
                "ad_creatives": [self._creative(advertiser_id, 1)],
                "serpapi_pagination": {"next_page_token": "tok"},
            }

        seen = capture(body)

        await connector("google_ads_transparency").pull(None, store)

        for advertiser_id in self._advertiser_ids():
            pages = [
                r for r in seen if r.url.params.get("advertiser_id") == advertiser_id
            ]
            assert [r.url.params.get("next_page_token") for r in pages] == [None, "tok"]
        creatives = {s["source_id"] for s in stored if s["object_type"] == "creatives"}
        assert creatives == {
            f"CR{advertiser_id}_{n}"
            for advertiser_id in self._advertiser_ids()
            for n in (1, 2)
        }


class TestGoogleAdsTransparencyWithNoCreatives(_SocialCapture):
    async def test_an_advertiser_with_no_creatives_keeps_its_id_and_the_files_domain(
        self, capture, store, stored
    ):
        from app.engine import competitors

        capture({"ad_creatives": [], "serpapi_pagination": {}})

        notes = await connector("google_ads_transparency").pull(None, store)

        assert notes is None
        assert [s for s in stored if s["object_type"] == "creatives"] == []
        advertisers = {
            s["source_id"]: s["raw_payload"]
            for s in stored
            if s["object_type"] == "advertisers"
        }
        assert advertisers == {
            str(spec["google_advertiser_id"]): {
                "id": str(spec["google_advertiser_id"]),
                "domain": str(spec["domain"]),
            }
            for spec in competitors.tracked().values()
        }


class _CompetitorWatchers(_SocialCapture):
    @staticmethod
    def _definitions():
        from app.engine import competitors

        return competitors.definitions()

    def _domains(self):
        competitors = self._definitions()["competitors"]
        return [str(spec["domain"]) for spec in competitors.values()]

    @staticmethod
    def _payloads(stored, object_type):
        return {
            s["source_id"]: s["raw_payload"]
            for s in stored
            if s["object_type"] == object_type
        }


class TestSerpAsksForEveryTrackedKeyword(_CompetitorWatchers):
    @staticmethod
    def _page(request):
        return {
            "search_metadata": {
                "status": "Success",
                "created_at": "2026-09-14 05:42:11 UTC",
            },
            "search_parameters": {
                "engine": "google",
                "q": request.url.params.get("q"),
            },
            "organic_results": [
                {
                    "position": 1,
                    "title": "Vidora",
                    "link": "https://vidora.ai/",
                    "snippet": "Paste a product URL.",
                },
                {
                    "position": 9,
                    "title": "Digital Workers",
                    "link": "https://www.hiredigitalworkers.com/ugc",
                    "snippet": "We run the tool.",
                },
            ],
        }

    async def test_it_runs_one_google_search_for_each_keyword(self, capture, store):
        seen = capture(self._page)

        await connector("serp").pull(None, store)

        assert {r.url.path for r in seen} == {"/search"}
        assert [r.url.params.get("q") for r in seen] == self._definitions()["keywords"]
        for request in seen:
            assert request.url.params.get("engine") == "google"
            assert request.url.params.get("api_key")

    async def test_every_result_carries_the_search_that_found_it(
        self, capture, store, stored
    ):
        capture(self._page)

        notes = await connector("serp").pull(None, store)

        assert notes is None
        assert {s["source"] for s in stored} == {"serp"}
        assert {s["object_type"] for s in stored} == {"organic_results"}
        rows = self._payloads(stored, "organic_results")
        keyword = self._definitions()["keywords"][0]
        row = rows[f"{keyword}|google|vidora.ai|2026-09-14"]
        assert row["_keyword"] == keyword
        assert row["_engine"] == "google"
        assert row["_domain"] == "vidora.ai"
        assert row["_checked_on"] == "2026-09-14"
        assert row["position"] == 1
        assert row["snippet"] == "Paste a product URL."

    async def test_one_row_per_keyword_per_domain_per_day(self, capture, store, stored):
        capture(self._page)

        await connector("serp").pull(None, store)

        keywords = self._definitions()["keywords"]
        assert set(self._payloads(stored, "organic_results")) == {
            f"{keyword}|google|{domain}|2026-09-14"
            for keyword in keywords
            for domain in ("vidora.ai", "hiredigitalworkers.com")
        }

    async def test_a_keyword_google_answered_nothing_for_stores_nothing(
        self, capture, store, stored
    ):
        capture({"error": "Google hasn't returned any results for this query."})

        notes = await connector("serp").pull(None, store)

        assert notes is None
        assert stored == []

    async def test_a_result_with_no_link_is_counted_rather_than_stored(
        self, capture, store, stored
    ):
        capture(
            {
                "search_metadata": {"created_at": "2026-09-14 05:42:11 UTC"},
                "search_parameters": {"engine": "google", "q": "ai ugc ads"},
                "organic_results": [{"position": 1, "title": "No link here"}],
            }
        )

        notes = await connector("serp").pull(None, store)

        assert stored == []
        assert notes == {"missing_id": len(self._definitions()["keywords"])}


class TestAiAnswersAsksEveryPromptOfEveryEngine(_CompetitorWatchers):
    @staticmethod
    def _reading(request):
        return {
            "prompt": request.url.params.get("prompt"),
            "engine": request.url.params.get("engine"),
            "checked_at": "2026-09-14T05:45:00Z",
            "mentions": [
                {
                    "brand": "Vidora",
                    "domain": "vidora.ai",
                    "mentioned": "yes",
                    "cited_url": "https://vidora.ai/",
                    "rank": 1,
                },
                {
                    "brand": "Clipwise",
                    "domain": "clipwise.io",
                    "mentioned": "no",
                    "cited_url": "",
                    "rank": 0,
                },
            ],
            "next": None,
        }

    def _pairs(self):
        doc = self._definitions()
        return {
            (prompt, engine) for prompt in doc["prompts"] for engine in doc["engines"]
        }

    async def test_it_reads_every_prompt_on_every_engine(self, capture, store):
        seen = capture(self._reading)

        await connector("ai_answers").pull(None, store)

        assert {r.url.path for r in seen} == {"/v1/mentions"}
        assert len(seen) == len(self._pairs())
        assert {
            (r.url.params.get("prompt"), r.url.params.get("engine")) for r in seen
        } == self._pairs()

    async def test_every_brand_row_carries_the_reading_it_came_from(
        self, capture, store, stored
    ):
        capture(self._reading)

        notes = await connector("ai_answers").pull(None, store)

        assert notes is None
        assert {s["source"] for s in stored} == {"ai_answers"}
        assert {s["object_type"] for s in stored} == {"mentions"}
        rows = self._payloads(stored, "mentions")
        assert set(rows) == {
            f"{prompt}|{engine}|{brand}|2026-09-14"
            for prompt, engine in self._pairs()
            for brand in ("Vidora", "Clipwise")
        }
        prompt, engine = sorted(self._pairs())[0]
        row = rows[f"{prompt}|{engine}|Vidora|2026-09-14"]
        assert row["_prompt"] == prompt
        assert row["_engine"] == engine
        assert row["_checked_on"] == "2026-09-14"
        assert row["rank"] == 1

    async def test_a_brand_that_was_not_named_is_still_a_row(
        self, capture, store, stored
    ):
        capture(self._reading)

        await connector("ai_answers").pull(None, store)

        rows = self._payloads(stored, "mentions")
        prompt, engine = sorted(self._pairs())[0]
        row = rows[f"{prompt}|{engine}|Clipwise|2026-09-14"]
        assert row["mentioned"] == "no"
        assert row["cited_url"] == ""
        assert row["rank"] == 0

    async def test_a_mention_with_no_brand_is_counted_rather_than_stored(
        self, capture, store, stored
    ):
        capture(
            {
                "prompt": "best ai ugc ad tool",
                "engine": "chatgpt",
                "checked_at": "2026-09-14T05:45:00Z",
                "mentions": [{"domain": "vidora.ai", "mentioned": "yes", "rank": 1}],
                "next": None,
            }
        )

        notes = await connector("ai_answers").pull(None, store)

        assert stored == []
        assert notes == {"missing_id": len(self._pairs())}


class TestCompetitorPagesScrapesEachCompetitor(_CompetitorWatchers):
    PATHS = ("/", "/pricing")

    @staticmethod
    def _scrape(url):
        return {
            "success": True,
            "data": {
                "markdown": "# Pricing\n\nThree plans, no per-render fees.",
                "metadata": {
                    "title": f"Title for {url}",
                    "description": "Plans and prices",
                    "sourceURL": url,
                    "url": url,
                    "statusCode": 200,
                },
            },
        }

    def _body(self, request):
        body = json.loads(request.content)
        if request.url.path == "/v2/map":
            return {
                "success": True,
                "links": [
                    {"url": f"{body['url']}{path}", "title": path, "description": ""}
                    for path in self.PATHS
                ],
            }
        if request.url.path == "/v2/scrape":
            return self._scrape(body["url"])
        raise AssertionError(f"unexpected {request.method} {request.url.path}")

    def _links(self):
        return [
            f"https://{domain}{path}"
            for domain in self._domains()
            for path in self.PATHS
        ]

    async def test_it_maps_each_site_then_scrapes_every_link_it_was_given(
        self, capture, store
    ):
        seen = capture(self._body)

        await connector("competitor_pages").pull(None, store)

        module = connector("competitor_pages")
        assert {r.method for r in seen} == {"POST"}
        assert [r.url.path for r in seen] == ["/v2/map", "/v2/scrape", "/v2/scrape"] * (
            len(self._domains())
        )
        maps = [json.loads(r.content) for r in seen if r.url.path == "/v2/map"]
        assert maps == [
            {
                "url": f"https://{domain}",
                "limit": module.MAP_LIMIT,
                "includeSubdomains": False,
            }
            for domain in self._domains()
        ]
        scrapes = [json.loads(r.content) for r in seen if r.url.path == "/v2/scrape"]
        assert scrapes == [
            {"url": link, "formats": ["markdown"], "onlyMainContent": True}
            for link in self._links()
        ]

    async def test_each_page_is_stored_as_it_arrived_stamped_with_when_and_whose(
        self, capture, store, stored
    ):
        capture(self._body)

        notes = await connector("competitor_pages").pull(None, store)

        assert notes is None
        assert {s["source"] for s in stored} == {"competitor_pages"}
        assert {s["object_type"] for s in stored} == {"pages"}
        rows = self._payloads(stored, "pages")
        assert set(rows) == set(self._links())
        domain = self._domains()[0]
        url = f"https://{domain}/pricing"
        assert rows[url] == {
            **self._scrape(url)["data"],
            "_fetched_at": clock.now().isoformat(),
            "_competitor_ref": domain,
        }

    @pytest.mark.parametrize("host", ["www.", "app.", "get."])
    async def test_a_page_on_any_host_under_the_crawl_carries_the_files_domain(
        self, capture, store, stored, host
    ):
        def body(request):
            if request.url.path == "/v2/map":
                return self._body(request)
            url = json.loads(request.content)["url"]
            return self._scrape(url.replace("https://", f"https://{host}"))

        capture(body)

        await connector("competitor_pages").pull(None, store)

        rows = self._payloads(stored, "pages")
        for domain in self._domains():
            assert rows[f"https://{host}{domain}/"]["_competitor_ref"] == domain

    async def test_a_scrape_that_did_not_succeed_is_counted_not_stored(
        self, capture, store, stored
    ):
        def body(request):
            if request.url.path == "/v2/map":
                return self._body(request)
            if json.loads(request.content)["url"].endswith("/pricing"):
                return {"success": False, "error": "Page failed to load"}
            return {"success": True}

        capture(body)

        notes = await connector("competitor_pages").pull(None, store)

        assert stored == []
        assert notes == {"failed_scrapes": len(self._links())}

    async def test_a_scrape_naming_no_source_url_is_counted_not_stored(
        self, capture, store, stored
    ):
        def body(request):
            if request.url.path == "/v2/map":
                return self._body(request)
            return {"success": True, "data": {"markdown": "x", "metadata": {}}}

        capture(body)

        notes = await connector("competitor_pages").pull(None, store)

        assert stored == []
        assert notes == {"missing_id": len(self._links())}

    async def test_a_site_whose_map_has_no_links_is_scraped_no_further(
        self, capture, store, stored
    ):
        seen = capture({"success": True, "links": []})

        notes = await connector("competitor_pages").pull(None, store)

        assert notes is None
        assert stored == []
        assert [r.url.path for r in seen] == ["/v2/map"] * len(self._domains())

    def test_a_page_is_observed_when_it_was_fetched(self):
        assert connector("competitor_pages").OBSERVED_AT == {"pages": "_fetched_at"}


BRIGHTDATA_DATASET = "gd_lyy3tktm25m4avu764"


class TestLinkedinPostsCollectsEachCompetitor(_CompetitorWatchers):
    @pytest.fixture(autouse=True)
    def waits(self, monkeypatch):
        seen = []

        async def _record(seconds):
            seen.append(seconds)

        monkeypatch.setattr(client, "_sleep", _record)
        return seen

    def _companies(self):
        return {
            str(spec["linkedin_url"]): str(spec["domain"])
            for spec in self._definitions()["competitors"].values()
        }

    @staticmethod
    def _slug(company_url):
        return company_url.rstrip("/").rsplit("/", 1)[-1]

    @classmethod
    def _post(cls, company_url):
        slug = cls._slug(company_url)
        return {
            "id": f"7241-{slug}",
            "url": f"https://www.linkedin.com/posts/{slug}_activity-7241-{slug}",
            "user_id": company_url,
            "post_text": "Boring is a strategy.",
            "date_posted": "2026-09-11T13:25:00.539Z",
            "num_likes": 372,
            "num_comments": 45,
            "post_type": "post",
            "account_type": "Organization",
            "user_followers": 18400,
            "hashtags": ["#ads"],
            "repost": {},
            "timestamp": "2026-09-15T19:12:08.000Z",
        }

    @staticmethod
    def _dead_page(company_url):
        return {
            "timestamp": "2026-09-15T19:12:08.000Z",
            "input": {"url": company_url},
            "error": "Activities are not found",
            "error_code": "dead_page",
        }

    def _vendor(self, statuses=("ready",), strip=(), dead=False, records=None):
        companies: dict = {}
        polls: dict = {}

        def handler(request):
            path = request.url.path
            if path == "/datasets/v3/trigger":
                company = json.loads(request.content)[0]["url"]
                snapshot = f"s_{self._slug(company)}"
                companies[snapshot] = company
                return {"snapshot_id": snapshot}
            snapshot = path.rsplit("/", 1)[-1]
            if path == f"/datasets/v3/progress/{snapshot}" and snapshot in companies:
                seen = polls.get(snapshot, 0)
                polls[snapshot] = seen + 1
                return {"status": statuses[min(seen, len(statuses) - 1)]}
            if path == f"/datasets/v3/snapshot/{snapshot}" and snapshot in companies:
                company = companies[snapshot]
                if records is not None:
                    return records(company)
                post = self._post(company)
                for key in strip:
                    post.pop(key)
                return [self._dead_page(company)] if dead else [post]
            raise AssertionError(f"unexpected {request.method} {path}")

        return handler

    async def test_it_triggers_a_discovery_for_each_company_url(self, capture, store):
        seen = capture(self._vendor())

        await connector("linkedin_posts").pull(None, store)

        triggers = [r for r in seen if r.url.path == "/datasets/v3/trigger"]
        assert {r.method for r in triggers} == {"POST"}
        assert [json.loads(r.content) for r in triggers] == [
            [{"url": company}] for company in self._companies()
        ]
        for request in triggers:
            assert dict(request.url.params) == {
                "dataset_id": BRIGHTDATA_DATASET,
                "type": "discover_new",
                "discover_by": "company_url",
                "format": "json",
                "include_errors": "true",
            }

    async def test_it_polls_until_the_snapshot_is_ready_then_reads_it(
        self, capture, store
    ):
        seen = capture(self._vendor(("running", "ready")))

        await connector("linkedin_posts").pull(None, store)

        expected = []
        for company in self._companies():
            snapshot = f"s_{self._slug(company)}"
            expected += [
                ("POST", "/datasets/v3/trigger"),
                ("GET", f"/datasets/v3/progress/{snapshot}"),
                ("GET", f"/datasets/v3/progress/{snapshot}"),
                ("GET", f"/datasets/v3/snapshot/{snapshot}"),
            ]
        assert [(r.method, r.url.path) for r in seen] == expected
        reads = [r for r in seen if "/snapshot/" in r.url.path]
        assert all(dict(r.url.params) == {"format": "json"} for r in reads)

    async def test_it_waits_between_polls_but_not_before_the_first(
        self, capture, store, waits
    ):
        capture(self._vendor(("starting", "running", "ready")))

        await connector("linkedin_posts").pull(None, store)

        assert len(waits) == 2 * len(self._companies())
        assert all(seconds > 0 for seconds in waits)

    async def test_a_snapshot_ready_at_once_is_read_without_waiting(
        self, capture, store, waits
    ):
        capture(self._vendor())

        await connector("linkedin_posts").pull(None, store)

        assert waits == []

    async def test_each_post_is_stored_as_it_arrived_under_the_company_asked_for(
        self, capture, store, stored
    ):
        capture(self._vendor())

        notes = await connector("linkedin_posts").pull(None, store)

        assert notes is None
        assert {s["source"] for s in stored} == {"linkedin_posts"}
        assert {s["object_type"] for s in stored} == {"posts"}
        expected = {}
        for company, domain in self._companies().items():
            post = self._post(company)
            expected[post["id"]] = {**post, "_competitor_ref": domain}
        assert self._payloads(stored, "posts") == expected

    async def test_a_post_with_no_id_is_stored_under_its_url(
        self, capture, store, stored
    ):
        capture(self._vendor(strip=("id",)))

        notes = await connector("linkedin_posts").pull(None, store)

        assert notes is None
        assert set(self._payloads(stored, "posts")) == {
            self._post(company)["url"] for company in self._companies()
        }

    async def test_a_post_with_neither_id_nor_url_is_counted_not_stored(
        self, capture, store, stored
    ):
        capture(self._vendor(strip=("id", "url")))

        notes = await connector("linkedin_posts").pull(None, store)

        assert stored == []
        assert notes == {"missing_id": len(self._companies())}

    async def test_a_company_page_the_vendor_could_not_read_is_counted_not_stored(
        self, capture, store, stored
    ):
        capture(self._vendor(dead=True))

        notes = await connector("linkedin_posts").pull(None, store)

        assert stored == []
        assert notes == {"dead_pages": len(self._companies())}

    async def test_a_dead_page_is_not_a_post_missing_its_id(
        self, capture, store, stored
    ):
        def records(company):
            orphan = self._post(company)
            orphan.pop("id")
            orphan.pop("url")
            return [self._dead_page(company), orphan, self._post(company)]

        capture(self._vendor(records=records))

        notes = await connector("linkedin_posts").pull(None, store)

        companies = len(self._companies())
        assert notes == {"dead_pages": companies, "missing_id": companies}
        assert set(self._payloads(stored, "posts")) == {
            self._post(company)["id"] for company in self._companies()
        }

    def test_linkedin_posts_read_no_share_count(self):
        labels = {
            line.key: line.label
            for line in mappings.load()
            if line.source == "linkedin_posts" and line.object_type == "posts"
        }
        assert labels["linkedin_posts.posts.num_likes"] == "likes"
        assert "shares" not in labels.values()
        assert not [key for key in labels if key.endswith(".num_shares")]

    async def test_a_snapshot_that_failed_leaves_a_note_and_stores_nothing(
        self, capture, store, stored
    ):
        seen = capture(self._vendor(("failed",)))

        notes = await connector("linkedin_posts").pull(None, store)

        assert stored == []
        assert notes == {"failed_snapshots": len(self._companies())}
        assert [r for r in seen if "/snapshot/" in r.url.path] == []
        polls = [r for r in seen if "/progress/" in r.url.path]
        assert len(polls) == len(self._companies())

    async def test_a_snapshot_never_ready_is_given_up_after_the_last_poll(
        self, capture, store, stored
    ):
        seen = capture(self._vendor(("running",)))

        notes = await connector("linkedin_posts").pull(None, store)

        module = connector("linkedin_posts")
        assert stored == []
        assert notes == {"unfinished_snapshots": len(self._companies())}
        assert [r for r in seen if "/snapshot/" in r.url.path] == []
        polls = [r for r in seen if "/progress/" in r.url.path]
        assert len(polls) == module.MAX_POLLS * len(self._companies())

    def test_a_post_is_observed_when_it_was_published(self):
        assert connector("linkedin_posts").OBSERVED_AT == {"posts": "date_posted"}


class TestCompetitorCredentials:
    @pytest.mark.parametrize(
        "source,prefix",
        [
            ("serp", "/serp"),
            ("ai_answers", "/answers"),
            ("competitor_pages", "/pages"),
            ("linkedin_posts", "/social-scrape"),
        ],
    )
    def test_each_watcher_reaches_its_own_prefix(self, source, prefix):
        assert creds.credentials_for(source).base_url.endswith(prefix)

    def test_the_ranking_key_travels_as_a_query_parameter(self):
        assert creds.credentials_for("serp").params == {"api_key": "mock_serpapi_key"}

    @pytest.mark.parametrize(
        "source,token",
        [
            ("ai_answers", "mock_ai_answers_token"),
            ("competitor_pages", "mock_competitor_pages_token"),
            ("linkedin_posts", "mock_linkedin_posts_token"),
        ],
    )
    def test_the_scrapers_carry_a_bearer_token(self, source, token):
        assert creds.credentials_for(source).headers["Authorization"] == (
            f"Bearer {token}"
        )


class TestTheWatchersAreCatalogued:
    @pytest.mark.parametrize(
        "source", ["serp", "ai_answers", "competitor_pages", "linkedin_posts"]
    )
    def test_each_watcher_sits_with_the_ad_libraries(self, source):
        row = catalog.entry(source)
        assert row["category"] == "Competitors"
        assert row["label"] != source
        assert row["unlocks"]


TWILIO_ACCOUNT = "AC-account-test-0000"
TWILIO_KEY_SID = "SK-key-test-0000"
TWILIO_KEY_SECRET = "twilio-secret-test-0000"
CALENDLY_TOKEN = "calendly-token-test-0000"
CALENDLY_USER = "https://api.calendly.com/users/USER-TEST-0000"
MIXPANEL_USERNAME = "mixpanel-user-test-0000"
MIXPANEL_SECRET = "mixpanel-secret-test-0000"
MIXPANEL_PROJECT = "7654321"
SHEETS_SPREADSHEET = "sheet-test-0000"
GA_PROPERTY = "987654321"
GADS_CUSTOMER = "9876543210"
LINKEDIN_ORGANIZATION = "urn:li:organization:7000"
META_ACCOUNTS = ["act_900001", "act_900002"]


class TestWhatTheConfiguredValuesDoToTheRequest:
    @pytest.fixture
    def capture(self, monkeypatch):
        seen = []

        def _install(body):
            def handler(request):
                seen.append(request)
                return httpx.Response(200, json=body)

            monkeypatch.setattr(client, "_transport", httpx.MockTransport(handler))
            return seen

        yield _install
        monkeypatch.setattr(client, "_transport", None)

    @staticmethod
    async def _pull(name, seen):
        async def store(session, **kwargs):
            pass

        await connector(name).pull(None, store)
        return seen

    def _twilio_environment(self, monkeypatch):
        monkeypatch.setenv("TWILIO_ACCOUNT_SID", TWILIO_ACCOUNT)
        monkeypatch.setenv("TWILIO_API_KEY_SID", TWILIO_KEY_SID)
        monkeypatch.setenv("TWILIO_API_KEY_SECRET", TWILIO_KEY_SECRET)

    def _mixpanel_environment(self, monkeypatch):
        monkeypatch.setenv("MIXPANEL_SERVICE_ACCOUNT_USERNAME", MIXPANEL_USERNAME)
        monkeypatch.setenv("MIXPANEL_SERVICE_ACCOUNT_SECRET", MIXPANEL_SECRET)
        monkeypatch.setenv("MIXPANEL_PROJECT_ID", MIXPANEL_PROJECT)

    async def test_twilio_paths_by_the_configured_account(self, capture, monkeypatch):
        self._twilio_environment(monkeypatch)
        seen = await self._pull("twilio", capture({"messages": [{"sid": "SM1"}]}))
        assert [r.url.path for r in seen] == [
            f"/2010-04-01/Accounts/{TWILIO_ACCOUNT}/Messages.json"
        ]
        assert TWILIO_KEY_SECRET not in str(seen[0].url)

    async def test_twilio_paths_by_the_stand_in_account_without_credentials(
        self, capture
    ):
        seen = await self._pull("twilio", capture({"messages": [{"sid": "SM1"}]}))
        assert [r.url.path for r in seen] == [
            "/2010-04-01/Accounts/mock_account_sid/Messages.json"
        ]

    async def test_calendly_asks_for_the_configured_users_events(
        self, capture, monkeypatch
    ):
        monkeypatch.setenv("CALENDLY_ACCESS_TOKEN", CALENDLY_TOKEN)
        monkeypatch.setenv("CALENDLY_USER_URI", CALENDLY_USER)
        seen = await self._pull("calendly", capture({"collection": []}))
        assert [r.url.path for r in seen] == ["/scheduled_events"]
        assert seen[0].url.params.get("user") == CALENDLY_USER
        assert seen[0].url.params.get("count") == "100"

    async def test_calendly_resolves_the_user_without_credentials(self, capture):
        seen = await self._pull("calendly", capture({"collection": []}))
        assert [r.url.path for r in seen] == ["/users/me", "/scheduled_events"]

    async def test_mixpanel_exports_the_configured_project(self, capture, monkeypatch):
        self._mixpanel_environment(monkeypatch)
        seen = await self._pull("mixpanel", capture({}))
        assert [r.url.path for r in seen] == ["/api/2.0/export"]
        assert seen[0].url.params.get("project_id") == MIXPANEL_PROJECT
        assert seen[0].url.params.get("from_date") == "2026-06-07"
        assert seen[0].url.params.get("to_date") == "2026-09-04"

    async def test_mixpanel_names_no_project_without_credentials(self, capture):
        seen = await self._pull("mixpanel", capture({}))
        assert seen[0].url.params.get("project_id") is None

    async def test_google_sheets_reads_the_configured_spreadsheet(
        self, capture, monkeypatch
    ):
        monkeypatch.setitem(
            creds._MOCK_VALUES, "google_sheets", {"spreadsheet_id": SHEETS_SPREADSHEET}
        )
        seen = await self._pull("google_sheets", capture({"values": []}))
        assert [r.url.path for r in seen] == [
            f"/spreadsheets/{SHEETS_SPREADSHEET}/values/Pipeline!A1:F20"
        ]

    async def test_google_sheets_reads_the_stand_in_spreadsheet_without_credentials(
        self, capture
    ):
        seen = await self._pull("google_sheets", capture({"values": []}))
        assert [r.url.path for r in seen] == [
            "/spreadsheets/mock_spreadsheet_id/values/Pipeline!A1:F20"
        ]

    async def test_google_analytics_reports_on_the_configured_property(
        self, capture, monkeypatch
    ):
        monkeypatch.setitem(
            creds._MOCK_VALUES, "google_analytics", {"property_id": GA_PROPERTY}
        )
        seen = await self._pull("google_analytics", capture({"rows": []}))
        assert [r.url.path for r in seen] == [f"/properties/{GA_PROPERTY}:runReport"]

    async def test_google_analytics_reports_on_the_stand_in_without_credentials(
        self, capture
    ):
        seen = await self._pull("google_analytics", capture({"rows": []}))
        assert [r.url.path for r in seen] == ["/properties/123456789:runReport"]

    async def test_google_ads_searches_the_configured_customer(
        self, capture, monkeypatch
    ):
        monkeypatch.setitem(
            creds._MOCK_VALUES, "google_ads", {"customer_id": GADS_CUSTOMER}
        )
        seen = await self._pull("google_ads", capture({}))
        assert len(seen) == 2
        assert {r.url.path for r in seen} == {
            f"/v24/customers/{GADS_CUSTOMER}/googleAds:searchStream"
        }

    async def test_google_ads_searches_the_stand_in_customer_without_credentials(
        self, capture
    ):
        seen = await self._pull("google_ads", capture({}))
        assert len(seen) == 2
        assert {r.url.path for r in seen} == {
            "/v24/customers/1234567890/googleAds:searchStream"
        }

    async def test_twitter_asks_the_configured_user_for_tweets(
        self, capture, monkeypatch
    ):
        monkeypatch.setitem(creds._MOCK_VALUES, "twitter", {"user_id": TWITTER_USER})
        seen = await self._pull("twitter", capture({"meta": {"result_count": 0}}))
        assert [r.url.path for r in seen] == [f"/2/users/{TWITTER_USER}/tweets"]

    async def test_twitter_asks_the_stand_in_user_without_credentials(self, capture):
        seen = await self._pull("twitter", capture({"meta": {"result_count": 0}}))
        assert [r.url.path for r in seen] == ["/2/users/me/tweets"]

    async def test_twitter_names_its_user_before_any_request_is_made(self, monkeypatch):
        monkeypatch.setenv("TWITTER_BEARER_TOKEN", "twitter-token-test-0000")
        with pytest.raises(creds.CredentialsError, match="TWITTER_USER_ID"):
            await connector("twitter").pull(None, None)

    async def test_linkedin_asks_for_the_configured_organization(
        self, capture, monkeypatch
    ):
        monkeypatch.setitem(
            creds._MOCK_VALUES, "linkedin", {"organization": LINKEDIN_ORGANIZATION}
        )
        seen = await self._pull("linkedin", capture({"elements": []}))
        assert [
            r.url.params.get("author")
            or r.url.params.get("organizationalEntity")
            or r.url.params.get("organization")
            for r in seen
        ] == [None, LINKEDIN_ORGANIZATION, LINKEDIN_ORGANIZATION, LINKEDIN_ORGANIZATION]

    async def test_linkedin_asks_for_the_stand_in_organization_without_credentials(
        self, capture
    ):
        seen = await self._pull("linkedin", capture({"elements": []}))
        assert seen[1].url.params.get("author") == "urn:li:organization:1"

    async def test_meta_asks_every_configured_account(self, capture, monkeypatch):
        monkeypatch.setitem(creds._MOCK_VALUES, "meta", {"account_ids": META_ACCOUNTS})
        seen = await self._pull("meta", capture({"data": []}))
        assert [r.url.path for r in seen] == [
            f"/v25.0/{account}/{leaf}"
            for account in META_ACCOUNTS
            for leaf in ("campaigns", "insights", "insights")
        ] + ["/v25.0/me/accounts"]

    async def test_meta_asks_the_stand_in_accounts_without_credentials(self, capture):
        seen = await self._pull("meta", capture({"data": []}))
        assert {r.url.path.split("/")[2] for r in seen} == {
            "act_000001",
            "act_000002",
            "act_000006",
            "act_000007",
            "me",
        }


class TestTheSecondPageIsAskedForAtTheSamePageSize:
    @pytest.fixture
    def walk(self, monkeypatch):
        def _install(pages):
            seen = []

            def handler(request):
                seen.append(request)
                return httpx.Response(200, json=pages(request))

            monkeypatch.setattr(client, "_transport", httpx.MockTransport(handler))
            return seen

        yield _install
        monkeypatch.setattr(client, "_transport", None)

    @pytest.fixture
    def store(self):
        async def _store(session, **kwargs):
            return None

        return _store

    async def test_stripe_keeps_its_page_size_and_filter_across_the_cursor(
        self, walk, store
    ):
        def pages(request):
            if request.url.params.get("starting_after"):
                return {"data": [{"id": "second"}], "has_more": False}
            return {"data": [{"id": "first"}], "has_more": True}

        seen = walk(pages)

        await stripe.pull(None, store)

        assert [(r.url.path, dict(r.url.params)) for r in seen] == [
            ("/v1/customers", {"limit": "100"}),
            ("/v1/customers", {"limit": "100", "starting_after": "first"}),
            ("/v1/subscriptions", {"limit": "100", "status": "all"}),
            (
                "/v1/subscriptions",
                {"limit": "100", "status": "all", "starting_after": "first"},
            ),
        ]

    async def test_klaviyo_carries_each_endpoints_own_page_size_onto_page_two(
        self, walk, store
    ):
        def pages(request):
            if request.url.params.get("page[cursor]"):
                return {"data": [{"id": "second"}], "links": {"next": None}}
            size = request.url.params.get("page[size]")
            return {
                "data": [{"id": "first"}],
                "links": {
                    "next": f"https://a.klaviyo.com{request.url.path}"
                    f"?page%5Bcursor%5D=cursor-two&page%5Bsize%5D={size}"
                },
            }

        seen = walk(pages)

        await connector("klaviyo").pull(None, store)

        assert [(r.url.path, dict(r.url.params)) for r in seen] == [
            ("/api/profiles", {"page[size]": "100"}),
            ("/api/profiles", {"page[size]": "100", "page[cursor]": "cursor-two"}),
            ("/api/flows", {"page[size]": "50"}),
            ("/api/flows", {"page[size]": "50", "page[cursor]": "cursor-two"}),
        ]

    async def test_intercom_keeps_its_page_size_across_the_cursor(self, walk, store):
        def pages(request):
            key = "data" if request.url.path == "/contacts" else "conversations"
            if request.url.params.get("starting_after"):
                return {key: [{"id": "second"}], "pages": {}}
            return {
                key: [{"id": "first"}],
                "pages": {"next": {"starting_after": "first"}},
            }

        seen = walk(pages)

        await connector("intercom").pull(None, store)

        assert [(r.url.path, dict(r.url.params)) for r in seen] == [
            ("/contacts", {"per_page": "150"}),
            ("/contacts", {"per_page": "150", "starting_after": "first"}),
            ("/conversations", {"per_page": "150"}),
            ("/conversations", {"per_page": "150", "starting_after": "first"}),
        ]

    async def test_calendly_keeps_its_page_size_across_the_page_token(
        self, walk, store
    ):
        def pages(request):
            if request.url.path == "/users/me":
                return {"resource": {"uri": CALENDLY_USER}}
            if request.url.path.endswith("/invitees"):
                return {"collection": [], "pagination": {}}
            if request.url.params.get("page_token"):
                return {"collection": [], "pagination": {}}
            return {
                "collection": [
                    {"uri": "https://api.calendly.com/scheduled_events/evt_1"}
                ],
                "pagination": {"next_page_token": "token-two"},
            }

        seen = walk(pages)

        await connector("calendly").pull(None, store)

        assert [(r.url.path, dict(r.url.params)) for r in seen] == [
            ("/users/me", {}),
            ("/scheduled_events", {"user": CALENDLY_USER, "count": "100"}),
            (
                "/scheduled_events",
                {
                    "user": CALENDLY_USER,
                    "count": "100",
                    "page_token": "token-two",
                },
            ),
            ("/scheduled_events/evt_1/invitees", {"count": "100"}),
        ]

    async def test_mailchimp_advances_the_offset_by_a_whole_page(self, walk, store):
        def pages(request):
            kind = request.url.path.rsplit("/", 1)[-1]
            return {kind: [{"id": "row"}], "total_items": 1500}

        seen = walk(pages)

        await connector("mailchimp").pull(None, store)

        assert [(r.url.path, dict(r.url.params)) for r in seen] == [
            ("/3.0/lists", {"count": "1000", "offset": "0"}),
            ("/3.0/lists", {"count": "1000", "offset": "1000"}),
            ("/3.0/campaigns", {"count": "1000", "offset": "0"}),
            ("/3.0/campaigns", {"count": "1000", "offset": "1000"}),
        ]

    async def test_activecampaign_walks_on_from_a_page_that_is_full(self, walk, store):
        def pages(request):
            kind = request.url.path.rsplit("/", 1)[-1]
            rows = 100 if request.url.params.get("offset") == "0" else 1
            return {
                kind: [{"id": str(n)} for n in range(rows)],
                "meta": {"total": "2450"},
            }

        seen = walk(pages)

        await connector("activecampaign").pull(None, store)

        assert [(r.url.path, dict(r.url.params)) for r in seen] == [
            ("/api/3/contacts", {"limit": "100", "offset": "0"}),
            ("/api/3/contacts", {"limit": "100", "offset": "100"}),
            ("/api/3/campaigns", {"limit": "100", "offset": "0"}),
            ("/api/3/campaigns", {"limit": "100", "offset": "100"}),
        ]
