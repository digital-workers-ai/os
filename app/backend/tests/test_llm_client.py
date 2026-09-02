import importlib

import anthropic
import httpx
import pytest

from app import config, llm


def api_error(message="boom"):
    return anthropic.APIError(message, httpx.Request("POST", "http://api"), body=None)


class Block:
    def __init__(self, text, kind="text"):
        self.text, self.type = text, kind


class Response:
    def __init__(
        self,
        content=None,
        stop_reason="end_turn",
        parsed_output=None,
        model="claude-test",
    ):
        self.content = content if content is not None else []
        self.stop_reason = stop_reason
        self.parsed_output = parsed_output
        self.model = model


class FakeMessages:
    def __init__(self, result=None, raises=None):
        self.result, self.raises = result, raises
        self.calls = []

    async def _answer(self, **kwargs):
        self.calls.append(kwargs)
        if self.raises:
            raise self.raises
        return self.result

    create = _answer
    parse = _answer


class FakeClient:
    def __init__(self, result=None, raises=None):
        self.messages = FakeMessages(result, raises)


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
        llm.reset()
        importlib.reload(llm)
        llm.reset()


class TestComplete:
    async def test_text_blocks_are_joined(self):
        client = FakeClient(Response([Block("one "), Block("two")]))
        assert await llm.complete("sys", "usr", client_override=client) == "one two"

    async def test_non_text_blocks_are_ignored(self):
        client = FakeClient(Response([Block("kept"), Block("dropped", "thinking")]))
        assert await llm.complete("sys", "usr", client_override=client) == "kept"

    async def test_the_model_and_token_cap_are_passed_through(self):
        client = FakeClient(Response([Block("ok")]))
        await llm.complete(
            "sys", "usr", model="m", max_tokens=7, client_override=client
        )
        sent = client.messages.calls[0]
        assert sent["model"] == "m" and sent["max_tokens"] == 7
        assert sent["system"] == "sys"
        assert sent["messages"] == [{"role": "user", "content": "usr"}]

    async def test_defaults_come_from_settings_when_not_given(self):
        client = FakeClient(Response([Block("ok")]))
        await llm.complete("sys", "usr", client_override=client)
        sent = client.messages.calls[0]
        assert sent["model"] == config.settings.COACHING_MODEL
        assert sent["max_tokens"] == config.settings.COACHING_MAX_TOKENS

    async def test_a_wire_error_becomes_an_llm_error_naming_its_cause(self):
        client = FakeClient(raises=api_error("upstream is down"))
        with pytest.raises(llm.LLMError) as caught:
            await llm.complete("sys", "usr", client_override=client)
        assert "APIError" in str(caught.value)
        assert "upstream is down" in str(caught.value)

    async def test_a_safety_refusal_is_named_rather_than_read_as_empty(self):
        client = FakeClient(Response([], stop_reason="refusal"))
        with pytest.raises(llm.LLMError, match="declined to answer"):
            await llm.complete("sys", "usr", client_override=client)

    @pytest.mark.parametrize("content", [[], [Block("")], [Block("   ")]])
    async def test_an_empty_answer_reports_the_stop_reason(self, content):
        client = FakeClient(Response(content, stop_reason="max_tokens"))
        with pytest.raises(llm.LLMError) as caught:
            await llm.complete("sys", "usr", client_override=client)
        assert "max_tokens" in str(caught.value)


class TestParse:
    async def test_the_parsed_object_and_the_answering_model_come_back(self):
        client = FakeClient(
            Response(parsed_output={"label": "pricing"}, model="claude-actual")
        )
        parsed, model = await llm.parse(
            model="asked-for",
            max_tokens=10,
            system="s",
            user="u",
            output_format=dict,
            client_override=client,
        )
        assert parsed == {"label": "pricing"}
        assert model == "claude-actual"

    async def test_the_schema_goes_to_the_wire(self):
        client = FakeClient(Response(parsed_output={}))
        await llm.parse(
            model="m",
            max_tokens=1,
            system="s",
            user="u",
            output_format="SCHEMA",
            client_override=client,
        )
        assert client.messages.calls[0]["output_format"] == "SCHEMA"

    async def test_a_wire_error_becomes_an_llm_error(self):
        client = FakeClient(raises=api_error())
        with pytest.raises(llm.LLMError):
            await llm.parse(
                model="m",
                max_tokens=1,
                system="s",
                user="u",
                output_format=dict,
                client_override=client,
            )

    async def test_a_validation_error_is_an_llm_error_too_not_a_traceback(self):
        client = FakeClient(raises=ValueError("2 validation errors for Reading"))
        with pytest.raises(llm.LLMError) as caught:
            await llm.parse(
                model="m",
                max_tokens=1,
                system="s",
                user="u",
                output_format=dict,
                client_override=client,
            )
        assert "ValueError" in str(caught.value)
        assert "2 validation errors" in str(caught.value)

    async def test_a_refusal_is_named(self):
        client = FakeClient(Response(stop_reason="refusal", parsed_output={"a": 1}))
        with pytest.raises(llm.LLMError, match="declined to answer"):
            await llm.parse(
                model="m",
                max_tokens=1,
                system="s",
                user="u",
                output_format=dict,
                client_override=client,
            )

    async def test_nothing_parsed_reports_the_stop_reason(self):
        client = FakeClient(Response(stop_reason="max_tokens", parsed_output=None))
        with pytest.raises(llm.LLMError) as caught:
            await llm.parse(
                model="m",
                max_tokens=1,
                system="s",
                user="u",
                output_format=dict,
                client_override=client,
            )
        assert "max_tokens" in str(caught.value)


class TestConverse:
    async def test_the_raw_response_is_returned_for_the_caller_to_loop_on(self):
        response = Response([Block("hi")])
        client = FakeClient(response)
        assert (
            await llm.converse(
                model="m",
                max_tokens=1,
                system="s",
                messages=[],
                tools=[],
                client_override=client,
            )
            is response
        )

    async def test_tools_and_messages_reach_the_wire_unchanged(self):
        client = FakeClient(Response([Block("hi")]))
        tools = [{"name": "get_metrics"}]
        messages = [{"role": "user", "content": "mrr?"}]
        await llm.converse(
            model="m",
            max_tokens=2,
            system="s",
            messages=messages,
            tools=tools,
            client_override=client,
        )
        sent = client.messages.calls[0]
        assert sent["tools"] == tools and sent["messages"] == messages

    async def test_a_wire_error_becomes_an_llm_error(self):
        client = FakeClient(raises=api_error("rate limited"))
        with pytest.raises(llm.LLMError, match="rate limited"):
            await llm.converse(
                model="m",
                max_tokens=1,
                system="s",
                messages=[],
                tools=[],
                client_override=client,
            )


class TestStartupRefusesAMisconfiguredDeploy:
    def test_a_clean_environment_boots_with_enrichment_off(self):
        assert config.validate_startup(env={}) is None

    def test_enrichment_on_without_a_credential_refuses_the_boot(self, monkeypatch):
        monkeypatch.setattr(config.settings, "ENRICHMENT_ENABLED", True)
        with pytest.raises(config.StartupError, match="ENRICHMENT_ENABLED"):
            config.validate_startup(env={})

    def test_the_api_key_satisfies_it(self, monkeypatch):
        monkeypatch.setattr(config.settings, "ENRICHMENT_ENABLED", True)
        config.validate_startup(env={"ANTHROPIC_API_KEY": "sk-something"})

    def test_a_credential_with_enrichment_off_is_allowed_but_unused(self):
        config.validate_startup(env={"ANTHROPIC_API_KEY": "sk-something"})

    def test_coaching_on_without_a_credential_refuses_the_boot(self, monkeypatch):
        monkeypatch.setattr(config.settings, "COACHING_ENABLED", True)
        with pytest.raises(config.StartupError, match="COACHING_ENABLED"):
            config.validate_startup(env={})

    def test_conversation_on_without_a_credential_refuses_the_boot(self, monkeypatch):
        monkeypatch.setattr(config.settings, "CONVERSATION_ENABLED", True)
        with pytest.raises(config.StartupError, match="CONVERSATION_ENABLED"):
            config.validate_startup(env={})


def test_enrichment_ships_off_by_default():
    assert config.settings.ENRICHMENT_ENABLED is False


def test_coaching_ships_off_by_default():
    assert config.settings.COACHING_ENABLED is False


def test_conversation_ships_off_by_default():
    assert config.settings.CONVERSATION_ENABLED is False
