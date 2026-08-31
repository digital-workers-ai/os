import pkgutil

import httpx
import pytest

from app.sources import client, creds, registry, util
from app.sources.hubspot import connector as hubspot
from app.sources.stripe import connector as stripe


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


class TestCredentials:
    def test_an_unknown_source_names_itself(self):
        with pytest.raises(KeyError, match="nope"):
            creds.credentials_for("nope")


class TestRegistry:
    def test_every_connector_module_is_discovered(self):
        assert set(registry.discover()) == {"hubspot", "stripe"}

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
