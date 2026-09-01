import importlib
import json
import pkgutil

import httpx
import pytest

from app import sync
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
}


def connector(name):
    return importlib.import_module(f"app.sources.{name}.connector")


@pytest.fixture
def pull(monkeypatch):
    def _run(module, body, *, text=None):
        stored = []

        def handler(request):
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
        assert all(r.url.params.get("per_page") == "8" for r in seen)
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
        assert {r.url.path for r in seen} == {"/api/profiles", "/api/flows"}
        assert all(r.url.params.get("page[size]") == "8" for r in seen)
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
        assert [r.url.path for r in seen] == ["/scheduled_events"]
        assert seen[0].url.params.get("count") == "2"
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
        assert len(ALL_SOURCES) == 27
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

        assert notes is None
        assert {r.url.path for r in seen} == {
            "/admin/api/2024-01/products.json",
            "/admin/api/2024-01/orders.json",
            "/admin/api/2024-01/customers.json",
        }
        assert all(r.url.params.get("limit") == "1" for r in seen)
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
        assert all(r.url.params.get("count") == "5" for r in seen)
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
        assert notes == {"missing_id": 2}

    async def test_meta_counts_an_insight_row_with_no_id(self, pull):
        notes, stored = await pull(connector("meta"), {"data": [{"no_id": True}]})
        assert stored == []
        assert notes["missing_id"] >= 1

    async def test_google_ads_reads_a_bare_dict_body(self, pull):
        notes, stored = await pull(
            connector("google_ads"), {"results": [{"campaign": {"id": "c9"}}]}
        )
        assert notes is None
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
        assert all(r.url.params.get("limit") == "8" for r in seen)
        assert all(r.headers.get("Api-Token") == "mock_ac_token" for r in seen)
        assert {(s["object_type"], s["source_id"]) for s in stored} == {
            ("contacts", "10"),
            ("campaigns", "20"),
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
    @pytest.mark.parametrize("name", ["amplitude", "mixpanel"])
    async def test_a_blank_line_is_skipped_silently(self, pull, name):
        notes, stored = await pull(
            connector(name), None, text='{"a":1}\n\n   \n{"a":2}'
        )
        assert len(stored) == 2
        assert notes is None

    @pytest.mark.parametrize("name", ["amplitude", "mixpanel"])
    async def test_a_malformed_line_is_counted_not_fatal(self, pull, name):
        notes, stored = await pull(
            connector(name), None, text='{"a":1}\nnot json at all\n{"a":2}'
        )
        assert len(stored) == 2
        assert notes == {"malformed_lines": 1}

    @pytest.mark.parametrize("name", ["amplitude", "mixpanel"])
    async def test_a_line_with_no_vendor_id_is_keyed_by_its_content(self, pull, name):
        _notes, stored = await pull(connector(name), None, text='{"no_id_here":1}')
        assert len(stored[0]["source_id"]) == 32
        assert stored[0]["object_type"] == "events"

    async def test_amplitude_prefers_the_vendor_insert_id(self, pull):
        _notes, stored = await pull(
            connector("amplitude"), None, text='{"insert_id":"abc","uuid":"z"}'
        )
        assert stored[0]["source_id"] == "abc"

    async def test_amplitude_falls_back_to_the_uuid(self, pull):
        _notes, stored = await pull(connector("amplitude"), None, text='{"uuid":"z"}')
        assert stored[0]["source_id"] == "z"

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

    async def test_twitter_stores_the_accounts_it_is_given(self, pull):
        notes, stored = await pull(connector("twitter"), {"data": [{"id": "a1"}]})
        assert notes is None
        assert [(s["object_type"], s["source_id"]) for s in stored] == [
            ("accounts", "a1")
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
        assert [r.url.path for r in seen] == ["/ad_accounts", "/ad_accounts"]
        assert all(r.url.params.get("page_size") == "1" for r in seen)
        assert seen[1].url.params.get("bookmark") == "b2"
        assert [(s["object_type"], s["source_id"]) for s in stored] == [
            ("ad_accounts", "aa1"),
            ("ad_accounts", "aa2"),
        ]

    async def test_linkedin_walks_the_page_token_with_its_three_headers(self, capture):
        def body(request):
            if request.url.params.get("pageToken") == "t1":
                return {"elements": [{"id": 102}], "metadata": {}}
            return {"elements": [{"id": 101}], "metadata": {"nextPageToken": "t1"}}

        seen = capture(body)
        stored = []

        async def store(session, **kwargs):
            stored.append(kwargs)

        notes = await connector("linkedin").pull(None, store)

        assert notes is None
        assert [r.url.path for r in seen] == ["/adAccounts", "/adAccounts"]
        assert all(r.url.params.get("q") == "search" for r in seen)
        assert all(r.url.params.get("pageSize") == "1" for r in seen)
        assert seen[1].url.params.get("pageToken") == "t1"
        for request in seen:
            assert request.headers.get("Authorization") == "Bearer mock_linkedin_token"
            assert request.headers.get("linkedin-version") == "202401"
            assert request.headers.get("x-restli-protocol-version") == "2.0.0"
        assert [(s["object_type"], s["source_id"]) for s in stored] == [
            ("ad_accounts", "101"),
            ("ad_accounts", "102"),
        ]


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
