import importlib

import anthropic


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
