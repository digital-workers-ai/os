import importlib
import pkgutil

import httpx
import pytest

from app.sources import client, creds, registry, util
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
