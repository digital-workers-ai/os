import pkgutil

import pytest

from app.engine import extract
from app.engine.extract import hubspot as hubspot_hook


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


class TestRegistry:
    def test_every_hook_is_declared_in_hook_sources(self):
        assert set(extract.hooks()) <= set(extract.HOOK_SOURCES)


class TestExtractRegistration:
    def test_a_hook_module_with_no_reshape_is_refused(self, monkeypatch):
        extract._reset()
        monkeypatch.setattr(
            pkgutil, "iter_modules", lambda path: [type("I", (), {"name": "broken"})()]
        )
        monkeypatch.setattr(
            extract.importlib, "import_module", lambda name: type("M", (), {})
        )
        with pytest.raises(extract.ExtractError, match="defines no reshape"):
            extract.hooks()
        extract._reset()

    def test_a_hook_for_an_unlisted_source_is_refused(self, monkeypatch):
        extract._reset()
        monkeypatch.setattr(
            pkgutil,
            "iter_modules",
            lambda path: [type("I", (), {"name": "invented"})()],
        )
        monkeypatch.setattr(
            extract.importlib,
            "import_module",
            lambda name: type(
                "M",
                (),
                {"reshape": staticmethod(lambda o, p: [p]), "SOURCE": "invented"},
            ),
        )
        with pytest.raises(extract.ExtractError):
            extract.hooks()
        extract._reset()

    def test_a_hook_that_returns_something_other_than_dicts_is_refused(
        self, monkeypatch
    ):
        extract._reset()
        monkeypatch.setattr(
            pkgutil, "iter_modules", lambda path: [type("I", (), {"name": "hubspot"})()]
        )
        monkeypatch.setattr(
            extract.importlib,
            "import_module",
            lambda name: type(
                "M",
                (),
                {"reshape": staticmethod(lambda o, p: "nope"), "SOURCE": "hubspot"},
            ),
        )
        with pytest.raises(extract.ExtractError, match="must return dicts"):
            extract.reshape("hubspot", "contacts", {})
        extract._reset()


class TestReshapeGrammar:
    def test_a_source_without_a_hook_passes_through(self):
        payload = {"id": "cus_1"}
        assert extract.reshape("stripe", "customers", payload) == [payload]

    def test_a_single_dict_return_is_wrapped(self, monkeypatch):
        monkeypatch.setattr(extract, "_cache", {"hubspot": lambda o, p: {"a": 1}})
        assert extract.reshape("hubspot", "contacts", {}) == [{"a": 1}]
