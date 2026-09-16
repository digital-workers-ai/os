import json
from datetime import UTC, datetime

import httpx
import pytest

from app.config import settings
from app.engine import checks, spy
from app.engine.pipeline import observed_at_for
from app.sources import catalog, client, creds, registry
from app.sources.gemini import extract

FIXTURES = checks.REAL_FIXTURES.parent / "mock" / "gemini"
INGESTED = datetime(2026, 9, 14, tzinfo=UTC)
TODAY = "2026-09-04"
QUERY = "best crm for small business"
SLUG = "best-crm-for-small-business"
MODEL = "google/gemini-3.5-flash-lite"
REDIRECT = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/"
PLUGINS = [{"id": "web", "engine": "native", "max_results": 5}]
NOTHING_NAMED = "The right pick depends on budget and team size."
ANSWER = (
    "HubSpot CRM is the usual pick, with Pipedrive close behind for pure sales "
    "teams. Zoho is the cheap one."
)


def _citation(url, title):
    return {
        "type": "url_citation",
        "url_citation": {"url": url, "title": title, "start_index": 0, "end_index": 0},
    }


def _redirect(domain, opaque="AUZIYQE"):
    return _citation(f"{REDIRECT}{opaque}", domain)


def _response(content="", annotations=None):
    message = {
        "role": "assistant",
        "content": content,
        "refusal": None,
        "reasoning": None,
    }
    if annotations is not None:
        message["annotations"] = list(annotations)
    return {
        "id": "gen-1756987200-0123456789abcdef0123",
        "object": "chat.completion",
        "created": 1756987200,
        "model": MODEL,
        "provider": "Google",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "native_finish_reason": "STOP",
                "message": message,
            }
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 40, "total_tokens": 52},
    }


def _request(query=QUERY):
    return {"engine": "gemini", "query": query, "checked_at": TODAY, "model": MODEL}


def _payload(content="", annotations=None):
    return {"request": _request(), "response": _response(content, annotations)}


def _mention(domain, name, role, rank):
    return {
        "_source_id": f"gemini|{SLUG}|{TODAY}|{domain}",
        "_mention_engine": "gemini",
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
        return await registry.get("gemini").pull(None, store)


class TestWhatTheConnectorAsksFor(_Capture):
    async def test_every_query_is_put_to_gemini_with_google_search_grounding(
        self, capture, store
    ):
        seen = capture(_response())
        await self._pull(store)
        bodies = [json.loads(request.content) for request in seen]
        assert [body["messages"] for body in bodies] == [
            [{"role": "user", "content": query}] for query in spy.definition().queries
        ]
        for request, body in zip(seen, bodies, strict=True):
            assert request.method == "POST"
            assert request.url.path == "/api/v1/chat/completions"
            assert request.headers["authorization"] == "Bearer mock_openrouter_key"
            assert set(body) == {"model", "messages", "plugins"}
            assert body["model"] == MODEL
            assert body["plugins"] == PLUGINS

    async def test_every_answer_is_stored_under_its_slug_and_the_day(
        self, capture, store, stored
    ):
        body = _response("HubSpot leads.", [_redirect("hubspot.com")])
        capture(body)
        notes = await self._pull(store)
        queries = spy.definition().queries
        assert [s["source_id"] for s in stored] == [
            f"{spy.slug(query)}|{TODAY}" for query in queries
        ]
        assert {(s["source"], s["object_type"]) for s in stored} == {
            ("gemini", "checks")
        }
        assert stored[0]["raw_payload"] == {
            "request": _request(queries[0]),
            "response": body,
        }
        assert notes is None


class TestTheHook:
    CITED = (
        _redirect("hubspot.com", "AUZIYQE"),
        _redirect("g2.com", "AUZIYQF"),
        _redirect("pipedrive.com", "AUZIYQG"),
    )

    def test_one_check_then_one_mention_per_company_in_the_answer(self):
        check, *found = extract.reshape("checks", _payload(ANSWER, self.CITED))
        assert check["_source_id"] == f"gemini|{SLUG}|{TODAY}"
        assert check["_engine"] == "gemini"
        assert check["_query"] == QUERY
        assert check["_checked_at"] == TODAY
        assert check["_answer"] == ANSWER
        assert check["_sources"] == 3
        assert check["_brand_rank"] == 2
        assert found == [
            _mention("hubspot.com", "HubSpot", "competitor", 1),
            _mention("pipedrive.com", "Pipedrive", "brand", 2),
            _mention("zoho.com", "Zoho CRM", "competitor", 3),
        ]

    def test_a_redirect_citation_is_linked_by_the_domain_in_its_title(self):
        payload = _payload(NOTHING_NAMED, [_redirect("freshworks.com")])
        check, *found = extract.reshape("checks", payload)
        assert check["_sources"] == 1
        assert found == [_mention("freshworks.com", "Freshsales", "competitor", 1)]

    def test_a_plain_url_citation_is_linked_by_its_url(self):
        cited = _citation("https://www.zoho.com/crm/", "Zoho CRM: Top-rated Sales CRM")
        check, *found = extract.reshape("checks", _payload(NOTHING_NAMED, [cited]))
        assert check["_sources"] == 1
        assert found == [_mention("zoho.com", "Zoho CRM", "competitor", 1)]

    def test_a_redirect_citation_without_a_title_keeps_the_redirect_url(self):
        cited = _citation(f"{REDIRECT}AUZIYQH", "")
        check, *found = extract.reshape("checks", _payload(NOTHING_NAMED, [cited]))
        assert check["_sources"] == 1
        assert found == []

    def test_a_company_only_cited_ranks_after_the_named_ones(self):
        cited = [_redirect("freshworks.com"), _redirect("hubspot.com", "AUZIYQF")]
        _check, *found = extract.reshape("checks", _payload("Pipedrive leads.", cited))
        assert [(m["_company"], m["_rank"]) for m in found] == [
            ("Pipedrive", 1),
            ("Freshsales", 2),
            ("HubSpot", 3),
        ]

    def test_the_brand_rank_is_absent_when_the_brand_is_not_mentioned(self):
        payload = _payload("HubSpot leads.", [_redirect("hubspot.com")])
        check, *found = extract.reshape("checks", payload)
        assert "_brand_rank" not in check
        assert [m["_role"] for m in found] == ["competitor"]

    def test_repeated_citations_count_once(self):
        cited = [
            _redirect("g2.com", "AUZIYQE"),
            _redirect("g2.com", "AUZIYQF"),
            _citation("https://www.capterra.com/p/crm", "Capterra"),
            _citation("https://www.capterra.com/p/crm", "Capterra"),
        ]
        check = extract.reshape("checks", _payload(NOTHING_NAMED, cited))[0]
        assert check["_sources"] == 2

    def test_the_check_keeps_the_payload_and_the_mentions_do_not(self):
        payload = _payload("HubSpot leads.", [_redirect("hubspot.com")])
        check, mention = extract.reshape("checks", payload)
        assert check["response"] == payload["response"]
        assert check["request"] == payload["request"]
        assert "response" not in mention
        assert "request" not in mention

    def test_an_answer_without_choices_is_an_empty_check(self):
        payload = {
            "request": _request(),
            "response": {"error": {"message": "Upstream failed", "code": 502}},
        }
        assert extract.reshape("checks", payload) == [
            {
                **payload,
                "_source_id": f"gemini|{SLUG}|{TODAY}",
                "_engine": "gemini",
                "_query": QUERY,
                "_checked_at": TODAY,
                "_answer": "",
                "_sources": 0,
            }
        ]

    @pytest.mark.parametrize(
        "response",
        [
            "gone",
            {"choices": "nope"},
            {"choices": []},
            {"choices": ["oops"]},
            {"choices": [{"message": "oops"}]},
            {"choices": [{"message": {"content": 7, "annotations": "nope"}}]},
            {
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "annotations": [
                                "oops",
                                {"url_citation": "no"},
                                {"url_citation": {"url": 5, "title": 6}},
                                {"url_citation": {"url": "", "title": "g2.com"}},
                                {"url_citation": {}},
                            ],
                        }
                    }
                ]
            },
        ],
    )
    def test_malformed_answers_do_not_raise(self, response):
        payload = {"request": _request(), "response": response}
        check, *found = extract.reshape("checks", payload)
        assert check["_answer"] == ""
        assert check["_sources"] == 0
        assert found == []

    def test_a_payload_with_nothing_in_it_still_yields_a_check(self):
        assert extract.reshape("checks", {}) == [
            {
                "_source_id": "gemini||",
                "_engine": "gemini",
                "_query": "",
                "_checked_at": "",
                "_answer": "",
                "_sources": 0,
            }
        ]

    def test_the_stored_payload_is_not_mutated(self):
        payload = _payload(ANSWER, self.CITED)
        extract.reshape("checks", payload)
        assert payload == _payload(ANSWER, self.CITED)


class TestOtherObjectTypes:
    def test_an_unknown_object_type_passes_through(self):
        payload = {"request": _request(), "models": []}
        assert extract.reshape("models", payload) == [payload]


class TestTheObservationPath:
    def test_checks_observe_the_day_the_query_was_asked(self):
        assert registry.get("gemini").OBSERVED_AT == {"checks": "request.checked_at"}

    def test_the_check_day_is_the_provider_observation(self):
        module = registry.get("gemini")
        payload = {"request": _request()}
        observed, which = observed_at_for(module, "checks", payload, INGESTED)
        assert which == "provider"
        assert observed == datetime(2026, 9, 4, tzinfo=UTC)


class TestCredentials:
    def test_the_stand_in_is_openrouter_behind_the_mock_with_the_mock_bearer(self):
        found = creds.credentials_for("gemini")
        assert found.base_url == f"{settings.MOCK_BASE_URL}/openrouter"
        assert found.headers == {"Authorization": "Bearer mock_openrouter_key"}
        assert found.params == {}
        assert found.auth is None
        assert found.real is False

    def test_the_openrouter_key_becomes_a_bearer_on_the_real_api(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-test-0000")
        found = creds.credentials_for("gemini")
        assert found.base_url == "https://openrouter.ai"
        assert found.headers == {"Authorization": "Bearer or-test-0000"}
        assert found.params == {}
        assert found.real is True


class TestCatalog:
    def test_gemini_is_listed_under_spy(self):
        assert catalog.entry("gemini") == {
            "source": "gemini",
            "label": "Gemini",
            "category": "Spy",
            "unlocks": "Brand and competitor mentions, cited sources",
        }


class TestTheMockFixture:
    @staticmethod
    def _rows():
        return json.loads((FIXTURES / "checks.json").read_text())

    def test_every_tracked_query_was_asked_once(self):
        rows = self._rows()
        assert [row["payload"]["request"]["query"] for row in rows] == list(
            spy.definition().queries
        )
        assert {row["payload"]["request"]["model"] for row in rows} == {MODEL}

    def test_every_answer_carries_text_and_grounding_citations(self):
        for row in self._rows():
            message = row["payload"]["response"]["choices"][0]["message"]
            assert message["content"]
            assert message["annotations"]

    def test_every_citation_is_a_redirect_titled_with_its_bare_domain(self):
        for row in self._rows():
            message = row["payload"]["response"]["choices"][0]["message"]
            for annotation in message["annotations"]:
                citation = annotation["url_citation"]
                assert citation["url"].startswith(REDIRECT)
                assert spy.host(citation["title"]) == citation["title"]
