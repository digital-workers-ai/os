import json
from datetime import UTC, datetime

import httpx
import pytest

from app.config import settings
from app.engine import checks, spy
from app.engine.pipeline import observed_at_for
from app.sources import catalog, client, creds, registry
from app.sources.chatgpt import connector, extract

FIXTURES = checks.REAL_FIXTURES.parent / "mock" / "chatgpt"
INGESTED = datetime(2026, 9, 14, tzinfo=UTC)
TODAY = "2026-09-04"
QUERY = "best crm for small business"
SLUG = "best-crm-for-small-business"
MODEL = "openai/gpt-5.6-luna"
PLUGIN = {"id": "web", "engine": "native", "max_results": 5}
HUBSPOT = "https://www.hubspot.com/pricing/suite?utm_source=openai"
PIPEDRIVE = "https://www.pipedrive.com/en/pricing?utm_source=openai"
G2 = "https://www.g2.com/categories/crm?utm_source=openai"


def _citation(url, title="A page"):
    return {
        "type": "url_citation",
        "url_citation": {"url": url, "title": title, "start_index": 0, "end_index": 0},
    }


def _completion(content, urls=(), *, annotations=None):
    message = {
        "role": "assistant",
        "content": content,
        "refusal": None,
        "reasoning": None,
    }
    if annotations is None:
        annotations = [_citation(url) for url in urls]
    if annotations is not False:
        message["annotations"] = annotations
    return {
        "id": "gen-1788609600-5WlfyzbKeCU25XiQWkP7",
        "object": "chat.completion",
        "created": 1788609600,
        "model": MODEL,
        "provider": "OpenAI",
        "system_fingerprint": None,
        "service_tier": "default",
        "choices": [
            {
                "index": 0,
                "logprobs": None,
                "finish_reason": "stop",
                "native_finish_reason": "completed",
                "message": message,
            }
        ],
        "usage": {
            "prompt_tokens": 21170,
            "completion_tokens": 957,
            "total_tokens": 22127,
            "cost": 0.02560135,
            "is_byok": False,
        },
    }


def _request(query=QUERY):
    return {"engine": "chatgpt", "query": query, "checked_at": TODAY, "model": MODEL}


def _payload(response, query=QUERY):
    return {"request": _request(query), "response": response}


def _mention(domain, name, role, rank):
    return {
        "_source_id": f"chatgpt|{SLUG}|{TODAY}|{domain}",
        "_mention_engine": "chatgpt",
        "_mention_query": QUERY,
        "_mention_checked_at": TODAY,
        "_company": name,
        "_role": role,
        "_rank": rank,
    }


class _Capture:
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

    @pytest.fixture
    def stored(self):
        return []

    @pytest.fixture
    def store(self, stored):
        async def _store(session, **kwargs):
            stored.append(kwargs)

        return _store

    @staticmethod
    async def _pull(store):
        return await registry.get("chatgpt").pull(None, store)


class TestWhatTheConnectorAsksFor(_Capture):
    async def test_every_query_is_asked_with_the_model_and_the_web_plugin(
        self, capture, store
    ):
        seen = capture(_completion("Nothing named."))
        await self._pull(store)
        spec = spy.definition()
        bodies = [json.loads(r.content) for r in seen]
        assert [b["messages"][0]["content"] for b in bodies] == list(spec.queries)
        for request, body, query in zip(seen, bodies, spec.queries, strict=True):
            assert request.method == "POST"
            assert request.url.path == "/api/v1/chat/completions"
            assert request.headers["authorization"] == "Bearer mock_openrouter_key"
            assert request.headers["content-type"] == "application/json"
            assert body == {
                "model": MODEL,
                "messages": [{"role": "user", "content": query}],
                "plugins": [PLUGIN],
            }

    async def test_every_check_is_stored_under_its_slug_and_the_day(
        self, capture, store, stored
    ):
        body = _completion("Pipedrive leads.", [PIPEDRIVE])
        capture(body)
        notes = await self._pull(store)
        spec = spy.definition()
        assert [s["source_id"] for s in stored] == [
            f"{spy.slug(q)}|{TODAY}" for q in spec.queries
        ]
        assert {s["source"] for s in stored} == {"chatgpt"}
        assert {s["object_type"] for s in stored} == {"checks"}
        assert stored[0]["raw_payload"] == {
            "request": _request(spec.queries[0]),
            "response": body,
        }
        assert notes is None

    def test_the_model_and_the_path_are_the_ones_the_capture_used(self):
        assert connector.MODEL == MODEL
        assert connector.PATH == "/api/v1/chat/completions"
        assert connector.SOURCE == "chatgpt"


class TestTheCheckHook:
    CONTENT = "HubSpot and Pipedrive lead the shortlist. Zoho CRM is the cheap one."

    def test_one_check_then_one_mention_per_company_named_or_cited(self):
        payload = _payload(_completion(self.CONTENT, [HUBSPOT, PIPEDRIVE, G2]))
        check, *found = extract.reshape("checks", payload)
        assert check["_source_id"] == f"chatgpt|{SLUG}|{TODAY}"
        assert check["_engine"] == "chatgpt"
        assert check["_query"] == QUERY
        assert check["_checked_at"] == TODAY
        assert check["_answer"] == self.CONTENT
        assert check["_sources"] == 3
        assert check["_brand_rank"] == 2
        assert found == [
            _mention("hubspot.com", "HubSpot", "competitor", 1),
            _mention("pipedrive.com", "Pipedrive", "brand", 2),
            _mention("zoho.com", "Zoho CRM", "competitor", 3),
        ]

    def test_the_check_keeps_the_payload_and_the_mentions_do_not(self):
        payload = _payload(_completion(self.CONTENT, [HUBSPOT]))
        check, first, *_rest = extract.reshape("checks", payload)
        assert check["request"] == payload["request"]
        assert check["response"] == payload["response"]
        assert "request" not in first
        assert "response" not in first

    def test_a_company_only_cited_ranks_after_the_named_ones(self):
        cited = "https://www.freshworks.com/crm/sales/?utm_source=openai"
        payload = _payload(_completion("Pipedrive leads.", [G2, cited]))
        check, *found = extract.reshape("checks", payload)
        assert check["_sources"] == 2
        assert [(m["_company"], m["_rank"]) for m in found] == [
            ("Pipedrive", 1),
            ("Freshsales", 2),
        ]

    def test_the_brand_rank_is_absent_when_the_brand_is_not_in_the_answer(self):
        payload = _payload(_completion("HubSpot leads.", [HUBSPOT]))
        check, *found = extract.reshape("checks", payload)
        assert "_brand_rank" not in check
        assert check["_sources"] == 1
        assert [m["_role"] for m in found] == ["competitor"]

    def test_repeated_citations_count_once(self):
        payload = _payload(_completion("Nothing named.", [G2, G2, HUBSPOT, G2]))
        check, *found = extract.reshape("checks", payload)
        assert check["_sources"] == 2
        assert [m["_company"] for m in found] == ["HubSpot"]

    @pytest.mark.parametrize(
        "response",
        [
            {},
            {"choices": []},
            {"choices": "nope"},
            {"choices": [None]},
            {"choices": [{"message": None}]},
            {"choices": [{"message": {"content": None}}]},
            {"choices": [{"message": {"content": ["parts"]}}]},
        ],
    )
    def test_an_answer_that_cannot_be_read_is_empty_with_no_mentions(self, response):
        payload = _payload(response)
        assert extract.reshape("checks", payload) == [
            {
                **payload,
                "_source_id": f"chatgpt|{SLUG}|{TODAY}",
                "_engine": "chatgpt",
                "_query": QUERY,
                "_checked_at": TODAY,
                "_answer": "",
                "_sources": 0,
            }
        ]

    def test_annotations_that_are_not_citations_are_skipped(self):
        annotations = [
            "oops",
            {"type": "url_citation"},
            {"type": "url_citation", "url_citation": "nope"},
            {"type": "url_citation", "url_citation": {"url": 5}},
            {"type": "url_citation", "url_citation": {"url": " "}},
            _citation("https://www.zoho.com/crm/?utm_source=openai"),
        ]
        payload = _payload(_completion("Nothing named.", annotations=annotations))
        check, *found = extract.reshape("checks", payload)
        assert check["_sources"] == 1
        assert [m["_company"] for m in found] == ["Zoho CRM"]

    def test_a_message_without_an_annotations_key_still_reads_the_answer(self):
        payload = _payload(_completion("Pipedrive leads.", annotations=False))
        check, *found = extract.reshape("checks", payload)
        assert check["_answer"] == "Pipedrive leads."
        assert check["_sources"] == 0
        assert check["_brand_rank"] == 1
        assert [m["_company"] for m in found] == ["Pipedrive"]

    def test_annotations_that_are_not_a_list_are_no_sources(self):
        payload = _payload(_completion("Nothing named.", annotations={"url": G2}))
        check, *found = extract.reshape("checks", payload)
        assert check["_sources"] == 0
        assert found == []

    def test_a_payload_with_nothing_in_it_still_yields_a_check(self):
        assert extract.reshape("checks", {}) == [
            {
                "_source_id": "chatgpt||",
                "_engine": "chatgpt",
                "_query": "",
                "_checked_at": "",
                "_answer": "",
                "_sources": 0,
            }
        ]

    def test_the_stored_payload_is_not_mutated(self):
        payload = _payload(_completion(self.CONTENT, [HUBSPOT]))
        extract.reshape("checks", payload)
        assert payload == _payload(_completion(self.CONTENT, [HUBSPOT]))


class TestOtherObjectTypes:
    def test_an_unknown_object_type_passes_through(self):
        payload = {"request": _request(), "models": []}
        assert extract.reshape("models", payload) == [payload]


class TestTheObservationPath:
    def test_checks_observe_the_day_the_query_was_asked(self):
        assert registry.get("chatgpt").OBSERVED_AT == {"checks": "request.checked_at"}

    def test_the_check_day_is_the_provider_observation(self):
        module = registry.get("chatgpt")
        payload = {"request": _request()}
        observed, which = observed_at_for(module, "checks", payload, INGESTED)
        assert which == "provider"
        assert observed == datetime(2026, 9, 4, tzinfo=UTC)


class TestCredentials:
    def test_the_stand_in_is_openrouter_behind_the_mock_with_the_mock_bearer(self):
        found = creds.credentials_for("chatgpt")
        assert found.base_url == f"{settings.MOCK_BASE_URL}/openrouter"
        assert found.headers == {"Authorization": "Bearer mock_openrouter_key"}
        assert found.params == {}
        assert found.auth is None
        assert found.real is False

    def test_the_real_key_travels_as_a_bearer(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-test-0000")
        found = creds.credentials_for("chatgpt")
        assert found.base_url == "https://openrouter.ai"
        assert found.headers == {"Authorization": "Bearer or-test-0000"}
        assert found.params == {}
        assert found.real is True


class TestCatalog:
    def test_chatgpt_is_listed_under_spy(self):
        assert catalog.entry("chatgpt") == {
            "source": "chatgpt",
            "label": "ChatGPT",
            "category": "Spy",
            "unlocks": "Brand and competitor mentions, cited sources",
        }


class TestTheMockFixture:
    @staticmethod
    def _rows():
        return json.loads((FIXTURES / "checks.json").read_text())

    def test_every_tracked_query_was_asked_once(self):
        rows = self._rows()
        assert [r["payload"]["request"]["query"] for r in rows] == list(
            spy.definition().queries
        )
        assert [r["source_id"] for r in rows] == [
            f"{spy.slug(q)}|{TODAY}" for q in spy.definition().queries
        ]

    def test_every_request_names_the_engine_and_the_model(self):
        for row in self._rows():
            request = row["payload"]["request"]
            assert request["engine"] == "chatgpt"
            assert request["model"] == MODEL
            assert request["checked_at"] == TODAY

    def test_every_answer_carries_text_and_openai_tagged_citations(self):
        for row in self._rows():
            message = row["payload"]["response"]["choices"][0]["message"]
            assert message["content"].strip()
            assert message["annotations"]
            for annotation in message["annotations"]:
                assert annotation["type"] == "url_citation"
                assert "utm_source=openai" in annotation["url_citation"]["url"]
