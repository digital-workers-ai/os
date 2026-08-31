import pkgutil

import pytest

from app.sources import hooks
from app.sources.hubspot import extract as hubspot_hook


def _info(name, ispkg=True):
    return type("I", (), {"name": name, "ispkg": ispkg})()


class TestCompositeNames:
    def test_hubspot_composes(self):
        out = hubspot_hook.reshape(
            "contacts", {"properties": {"firstname": "Jane", "lastname": "Smith"}}
        )
        assert out[0]["_full_name"] == "Jane Smith"

    def test_hubspot_handles_a_missing_half(self):
        out = hubspot_hook.reshape("contacts", {"properties": {"lastname": "Smith"}})
        assert out[0]["_full_name"] == "Smith"

    def test_hubspot_omits_the_field_entirely_when_there_is_no_name(self):
        out = hubspot_hook.reshape("contacts", {"properties": {}})
        assert "_full_name" not in out[0]

    def test_companies_pass_through(self):
        payload = {"properties": {"name": "Acme"}}
        assert hubspot_hook.reshape("companies", payload) == [payload]


class TestDiscovery:
    def test_every_source_package_with_an_extract_module_is_a_hook(self):
        assert set(hooks.hooks()) == {"hubspot"}

    def test_a_package_without_an_extract_module_contributes_no_hook(self, monkeypatch):
        hooks._reset()
        monkeypatch.setattr(pkgutil, "iter_modules", lambda path: [_info("bare")])
        monkeypatch.setattr(hooks.importlib.util, "find_spec", lambda name: None)
        assert hooks.hooks() == {}
        hooks._reset()

    def test_an_extract_module_with_no_reshape_is_refused(self, monkeypatch):
        hooks._reset()
        monkeypatch.setattr(pkgutil, "iter_modules", lambda path: [_info("broken")])
        monkeypatch.setattr(hooks.importlib.util, "find_spec", lambda name: object())
        monkeypatch.setattr(
            hooks.importlib, "import_module", lambda name: type("M", (), {})
        )
        with pytest.raises(hooks.ExtractError, match="defines no reshape"):
            hooks.hooks()
        hooks._reset()

    def test_a_hook_that_returns_something_other_than_dicts_is_refused(
        self, monkeypatch
    ):
        monkeypatch.setattr(hooks, "_cache", {"hubspot": lambda o, p: "nope"})
        with pytest.raises(hooks.ExtractError, match="must return dicts"):
            hooks.reshape("hubspot", "contacts", {})


class TestReshapeGrammar:
    def test_a_source_without_a_hook_passes_through(self):
        payload = {"id": "cus_1"}
        assert hooks.reshape("stripe", "customers", payload) == [payload]

    def test_a_single_dict_return_is_wrapped(self, monkeypatch):
        monkeypatch.setattr(hooks, "_cache", {"hubspot": lambda o, p: {"a": 1}})
        assert hooks.reshape("hubspot", "contacts", {}) == [{"a": 1}]
