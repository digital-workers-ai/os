import json
from datetime import UTC, datetime

import httpx
import pytest

from app.config import settings
from app.engine import checks, spy
from app.engine.pipeline import observed_at_for
from app.sources import catalog, client, creds, registry
from app.sources.perplexity import extract

FIXTURES = checks.REAL_FIXTURES.parent / "mock" / "perplexity"
INGESTED = datetime(2026, 9, 14, tzinfo=UTC)
TODAY = "2026-09-04"
QUERY = "best crm for small business"
SLUG = "best-crm-for-small-business"
MODEL = "perplexity/sonar"
PATH = "/api/v1/chat/completions"
HUBSPOT = "https://www.hubspot.com/products/crm"
PIPEDRIVE = "https://www.pipedrive.com/en/features"
ZOHO = "https://www.zoho.com/crm/"
FRESHWORKS = "https://www.freshworks.com/crm/sales/"
G2 = "https://www.g2.com/categories/crm"


def _citation(url):
    return {
        "type": "url_citation",
        "url_citation": {
            "url": url,
            "title": spy.host(url),
            "start_index": 0,
            "end_index": 0,
        },
    }


def _completion(content, annotations=None):
    message = {
        "role": "assistant",
        "content": content,
        "refusal": None,
        "reasoning": None,
    }
    if annotations is not None:
        message["annotations"] = annotations
    return {
        "id": "gen-1789528670-69G3NWBcgFD1qVNA4n0h",
        "object": "chat.completion",
        "created": 1789528670,
        "model": MODEL,
        "provider": "Perplexity",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "native_finish_reason": "stop",
                "message": message,
            }
        ],
        "usage": {"prompt_tokens": 6, "completion_tokens": 42, "total_tokens": 48},
    }


def _request(query=QUERY):
    return {
        "engine": "perplexity",
        "query": query,
        "checked_at": TODAY,
        "model": MODEL,
    }


def _payload(content, annotations=None, query=QUERY):
    return {"request": _request(query), "response": _completion(content, annotations)}


def _mention(domain, name, role, rank, query=QUERY):
    return {
        "_source_id": f"perplexity|{spy.slug(query)}|{TODAY}|{domain}",
        "_mention_engine": "perplexity",
        "_mention_query": query,
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
        return await registry.get("perplexity").pull(None, store)


class TestWhatTheConnectorAsksFor(_Capture):
    async def test_every_query_is_put_to_sonar_without_the_web_plugin(
        self, capture, store
    ):
        seen = capture(_completion("Nothing named."))
        await self._pull(store)
        bodies = [json.loads(request.content) for request in seen]
        assert [body["messages"] for body in bodies] == [
            [{"role": "user", "content": query}] for query in spy.definition().queries
        ]
        for request, body in zip(seen, bodies, strict=True):
            assert request.method == "POST"
            assert request.url.path == PATH
            assert request.headers["Authorization"] == "Bearer mock_openrouter_key"
            assert body == {"model": MODEL, "messages": body["messages"]}

    async def test_every_answer_is_stored_under_its_slug_and_the_day(
        self, capture, store, stored
    ):
        body = _completion("Pipedrive leads.[1]", [_citation(PIPEDRIVE)])
        capture(body)
        notes = await self._pull(store)
        spec = spy.definition()
        assert [s["source_id"] for s in stored] == [
            f"{spy.slug(q)}|{TODAY}" for q in spec.queries
        ]
        assert {s["source"] for s in stored} == {"perplexity"}
        assert {s["object_type"] for s in stored} == {"checks"}
        assert stored[0]["raw_payload"] == {
            "request": _request(spec.queries[0]),
            "response": body,
        }
        assert notes is None


class TestTheHook:
    ANSWER = (
        "HubSpot CRM and Pipedrive lead the shortlist.[1][2] Zoho is the cheap one.[3]"
    )
    CITED = (_citation(HUBSPOT), _citation(PIPEDRIVE), _citation(G2))

    def test_one_check_then_one_mention_per_company_in_the_answer(self):
        payload = _payload(self.ANSWER, list(self.CITED))
        check, *found = extract.reshape("checks", payload)
        assert check["_source_id"] == f"perplexity|{SLUG}|{TODAY}"
        assert check["_engine"] == "perplexity"
        assert check["_query"] == QUERY
        assert check["_checked_at"] == TODAY
        assert check["_answer"] == self.ANSWER
        assert check["_sources"] == 3
        assert check["_brand_rank"] == 2
        assert found == [
            _mention("hubspot.com", "HubSpot", "competitor", 1),
            _mention("pipedrive.com", "Pipedrive", "brand", 2),
            _mention("zoho.com", "Zoho CRM", "competitor", 3),
        ]

    def test_the_check_keeps_the_payload_and_the_mentions_do_not(self):
        payload = _payload(self.ANSWER, list(self.CITED))
        check, first, *_rest = extract.reshape("checks", payload)
        assert check["request"] == payload["request"]
        assert check["response"] == payload["response"]
        assert "request" not in first
        assert "response" not in first

    def test_the_brand_rank_is_absent_when_the_brand_is_not_mentioned(self):
        payload = _payload("HubSpot leads.[1]", [_citation(HUBSPOT)])
        check, *found = extract.reshape("checks", payload)
        assert "_brand_rank" not in check
        assert check["_sources"] == 1
        assert [m["_role"] for m in found] == ["competitor"]

    def test_a_company_only_cited_ranks_after_the_named_ones(self):
        payload = _payload("Pipedrive leads.[1]", [_citation(FRESHWORKS)])
        _check, *found = extract.reshape("checks", payload)
        assert [(m["_company"], m["_rank"]) for m in found] == [
            ("Pipedrive", 1),
            ("Freshsales", 2),
        ]

    def test_citations_are_read_in_the_order_sonar_numbers_them(self):
        cited = [_citation(ZOHO), _citation(HUBSPOT)]
        payload = _payload("Nothing named.[1][2]", cited)
        _check, *found = extract.reshape("checks", payload)
        assert [(m["_company"], m["_rank"]) for m in found] == [
            ("Zoho CRM", 1),
            ("HubSpot", 2),
        ]

    def test_a_page_cited_twice_counts_once(self):
        cited = [_citation(G2), _citation(G2), _citation(HUBSPOT)]
        check, *found = extract.reshape("checks", _payload("Nothing named.", cited))
        assert check["_sources"] == 2
        assert [m["_company"] for m in found] == ["HubSpot"]

    @pytest.mark.parametrize(
        "response",
        [
            {},
            {"choices": []},
            {"choices": "gone"},
            {"choices": ["gone"]},
            {"choices": [{"message": "gone"}]},
            {"choices": [{"message": {"content": None}}]},
            {"choices": [{"message": {"content": 7, "annotations": "gone"}}]},
        ],
    )
    def test_an_answer_without_a_readable_message_is_an_empty_check(self, response):
        payload = {"request": _request(), "response": response}
        assert extract.reshape("checks", payload) == [
            {
                **payload,
                "_source_id": f"perplexity|{SLUG}|{TODAY}",
                "_engine": "perplexity",
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
            {"type": "url_citation", "url_citation": "gone"},
            {"type": "url_citation", "url_citation": {"url": 5}},
            {"type": "url_citation", "url_citation": {"url": " "}},
            _citation(HUBSPOT),
        ]
        payload = _payload("Nothing named.", annotations)
        check, *found = extract.reshape("checks", payload)
        assert check["_sources"] == 1
        assert [m["_company"] for m in found] == ["HubSpot"]

    def test_a_payload_with_nothing_in_it_still_yields_a_check(self):
        assert extract.reshape("checks", {}) == [
            {
                "_source_id": "perplexity||",
                "_engine": "perplexity",
                "_query": "",
                "_checked_at": "",
                "_answer": "",
                "_sources": 0,
            }
        ]

    def test_the_stored_payload_is_not_mutated(self):
        payload = _payload(self.ANSWER, list(self.CITED))
        extract.reshape("checks", payload)
        assert payload == _payload(self.ANSWER, list(self.CITED))


class TestOtherObjectTypes:
    def test_an_unknown_object_type_passes_through(self):
        payload = {"request": _request(), "models": []}
        assert extract.reshape("models", payload) == [payload]


class TestTheObservationPath:
    def test_a_check_observes_the_day_the_query_was_asked(self):
        assert registry.get("perplexity").OBSERVED_AT == {
            "checks": "request.checked_at"
        }

    def test_the_check_day_is_the_provider_observation(self):
        module = registry.get("perplexity")
        payload = {"request": _request()}
        observed, which = observed_at_for(module, "checks", payload, INGESTED)
        assert which == "provider"
        assert observed == datetime(2026, 9, 4, tzinfo=UTC)


class TestCredentials:
    def test_the_stand_in_is_openrouter_behind_the_mock_with_the_mock_bearer(self):
        found = creds.credentials_for("perplexity")
        assert found.base_url == f"{settings.MOCK_BASE_URL}/openrouter"
        assert found.headers == {"Authorization": "Bearer mock_openrouter_key"}
        assert found.params == {}
        assert found.auth is None
        assert found.real is False

    def test_the_real_key_travels_as_a_bearer(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-test-0000")
        found = creds.credentials_for("perplexity")
        assert found.base_url == "https://openrouter.ai"
        assert found.headers == {"Authorization": "Bearer or-test-0000"}
        assert found.params == {}
        assert found.real is True


class TestCatalog:
    def test_perplexity_is_listed_under_spy(self):
        assert catalog.entry("perplexity") == {
            "source": "perplexity",
            "label": "Perplexity",
            "category": "Spy",
            "unlocks": "Brand and competitor mentions, cited sources",
        }


class TestTheMockFixture:
    @staticmethod
    def _rows():
        return json.loads((FIXTURES / "checks.json").read_text())

    def test_every_tracked_query_was_asked_once(self):
        queries = [row["payload"]["request"]["query"] for row in self._rows()]
        assert queries == list(spy.definition().queries)

    def test_every_check_is_filed_under_its_slug_and_the_day(self):
        for row in self._rows():
            request = row["payload"]["request"]
            assert request["engine"] == "perplexity"
            assert request["model"] == MODEL
            slug = spy.slug(request["query"])
            assert row["source_id"] == f"{slug}|{request['checked_at']}"

    def test_every_answer_came_from_sonar_with_citations(self):
        for row in self._rows():
            response = row["payload"]["response"]
            assert response["model"] == MODEL
            message = response["choices"][0]["message"]
            assert message["content"]
            assert message["annotations"]
