import importlib

import anthropic
import pytest

from app import config


class TestClientLifecycle:
    def test_the_client_is_built_once_and_reused(self, monkeypatch):
        llm = importlib.import_module("app.llm")
        built = []

        class Fake:
            def __init__(self):
                built.append(self)

        monkeypatch.setattr(anthropic, "AsyncAnthropic", Fake)
        llm.reset()
        first, second = llm.client(), llm.client()
        assert first is second
        assert len(built) == 1
        llm.reset()

    def test_reset_drops_the_cached_client(self, monkeypatch):
        llm = importlib.import_module("app.llm")
        monkeypatch.setattr(anthropic, "AsyncAnthropic", lambda: object())
        llm.reset()
        first = llm.client()
        llm.reset()
        assert llm.client() is not first
        llm.reset()

    def test_importing_the_module_never_needs_a_credential(self, monkeypatch):
        llm = importlib.import_module("app.llm")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
        llm.reset()
        importlib.reload(llm)
        llm.reset()


class TestStartupRefusesAMisconfiguredDeploy:
    def test_a_clean_environment_boots_with_enrichment_off(self):
        assert config.validate_startup(env={}) is None

    def test_enrichment_on_without_a_credential_refuses_the_boot(self, monkeypatch):
        monkeypatch.setattr(config.settings, "ENRICHMENT_ENABLED", True)
        with pytest.raises(config.StartupError, match="ENRICHMENT_ENABLED"):
            config.validate_startup(env={})

    @pytest.mark.parametrize("name", ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"])
    def test_either_credential_form_satisfies_it(self, name, monkeypatch):
        monkeypatch.setattr(config.settings, "ENRICHMENT_ENABLED", True)
        config.validate_startup(env={name: "sk-something"})

    def test_a_credential_with_enrichment_off_is_allowed_but_unused(self):
        config.validate_startup(env={"ANTHROPIC_API_KEY": "sk-something"})


def test_enrichment_ships_off_by_default():
    assert config.settings.ENRICHMENT_ENABLED is False
