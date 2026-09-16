import json
from datetime import UTC, datetime

import httpx
import pytest

from app.config import settings
from app.engine import checks, spy
from app.engine.pipeline import observed_at_for
from app.sources import catalog, client, creds, registry
from app.sources.claude import extract

FIXTURES = checks.REAL_FIXTURES.parent / "mock" / "claude"
INGESTED = datetime(2026, 9, 14, tzinfo=UTC)
TODAY = "2026-09-04"
QUERY = "best crm for small business"
SLUG = "best-crm-for-small-business"
MODEL = "claude-haiku-4-5"
TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 3}
TOOL_USE_ID = "srvtoolu_01Js6anQWAzUPu3zpJ4M1oJn"
PIPEDRIVE = "https://www.pipedrive.com/en/features/sales-pipeline"
HUBSPOT = "https://www.hubspot.com/products/crm"
ZOHO = "https://www.zoho.com/crm/sales-automation.html"
FRESHWORKS = "https://www.freshworks.com/crm/sales/"
G2 = "https://www.g2.com/categories/crm"


def _citation(url):
    return {
        "type": "web_search_result_location",
        "cited_text": "A page about CRMs.",
        "url": url,
        "title": "A page about CRMs",
        "encrypted_index": "Eo8BCioIExgCIiQ2NzI0ZDFj",
    }


def _text(text, *urls):
    block = {"type": "text", "text": text}
    if urls:
        return {"citations": [_citation(url) for url in urls], **block}
    return block


def _result(url):
    return {
        "type": "web_search_result",
        "title": "A page about CRMs",
        "url": url,
        "encrypted_content": "EsQICioIExgCIiQ2NzI0ZDFj",
        "page_age": None,
    }


def _search(content):
    return [
        {
            "type": "server_tool_use",
            "id": TOOL_USE_ID,
            "name": "web_search",
            "input": {"query": f"{QUERY} 2026"},
        },
        {
            "type": "web_search_tool_result",
            "tool_use_id": TOOL_USE_ID,
            "content": content,
            "caller": {"type": "direct"},
        },
    ]


def _searched(*urls):
    return _search([_result(url) for url in urls])


def _message(content):
    return {
        "model": "claude-haiku-4-5-20251001",
        "id": "msg_011Cf6Qnc6D6oXqDtPLcxLcm",
        "type": "message",
        "role": "assistant",
        "content": list(content),
        "container": None,
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "stop_details": None,
        "usage": {"input_tokens": 8875, "output_tokens": 586},
    }


def _request(query=QUERY):
    return {"engine": "claude", "query": query, "checked_at": TODAY, "model": MODEL}


def _payload(content, query=QUERY):
    return {"request": _request(query), "response": _message(content)}


def _check(payload, answer, sources, query=QUERY):
    return {
        **payload,
        "_source_id": f"claude|{spy.slug(query)}|{TODAY}",
        "_engine": "claude",
        "_query": query,
        "_checked_at": TODAY,
        "_answer": answer,
        "_sources": sources,
    }


def _mention(domain, name, role, rank, query=QUERY):
    return {
        "_source_id": f"claude|{spy.slug(query)}|{TODAY}|{domain}",
        "_mention_engine": "claude",
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

        def _install(message):
            def handler(request):
                seen.append(request)
                return httpx.Response(200, json=message)

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
        return await registry.get("claude").pull(None, store)


class TestWhatTheConnectorAsksFor(_Capture):
    async def test_every_query_is_put_to_haiku_with_the_web_search_tool(
        self, capture, store
    ):
        seen = capture(_message([_text("Nothing named.")]))
        await self._pull(store)
        bodies = [json.loads(request.content) for request in seen]
        assert [body["messages"] for body in bodies] == [
            [{"role": "user", "content": query}] for query in spy.definition().queries
        ]
        for request, body in zip(seen, bodies, strict=True):
            assert request.method == "POST"
            assert request.url.path == "/v1/messages"
            assert request.headers["x-api-key"] == "mock_anthropic_key"
            assert request.headers["anthropic-version"] == "2023-06-01"
            assert body == {
                "model": MODEL,
                "max_tokens": 1024,
                "messages": body["messages"],
                "tools": [TOOL],
            }

    async def test_every_answer_is_stored_whole_under_its_slug_and_the_day(
        self, capture, store, stored
    ):
        content = [*_searched(PIPEDRIVE), _text("Pipedrive leads.", PIPEDRIVE)]
        message = _message(content)
        capture(message)
        notes = await self._pull(store)
        spec = spy.definition()
        assert [s["source_id"] for s in stored] == [
            f"{spy.slug(query)}|{TODAY}" for query in spec.queries
        ]
        assert {s["source"] for s in stored} == {"claude"}
        assert {s["object_type"] for s in stored} == {"checks"}
        assert stored[0]["raw_payload"] == {
            "request": _request(spec.queries[0]),
            "response": message,
        }
        assert notes is None


class TestTheHook:
    CONTENT = (
        _text("I'll search for current information about CRMs."),
        *_searched(G2, HUBSPOT, PIPEDRIVE),
        _text("Based on recent information:\n\n**HubSpot**\n"),
        _text("HubSpot is free to start.", HUBSPOT),
        _text(" "),
        _text("Pipedrive is the visual one.", PIPEDRIVE),
        _text(" Consider your budget."),
    )

    def test_the_answer_is_every_text_block_joined_by_newlines(self):
        check = extract.reshape("checks", _payload(self.CONTENT))[0]
        assert check["_answer"] == (
            "I'll search for current information about CRMs.\n"
            "Based on recent information:\n\n**HubSpot**\n\n"
            "HubSpot is free to start.\n"
            " \n"
            "Pipedrive is the visual one.\n"
            " Consider your budget."
        )
        assert check["_source_id"] == f"claude|{SLUG}|{TODAY}"
        assert check["_engine"] == "claude"
        assert check["_query"] == QUERY
        assert check["_checked_at"] == TODAY

    def test_one_check_then_one_mention_per_company_in_the_answer(self):
        check, *found = extract.reshape("checks", _payload(self.CONTENT))
        assert check["_sources"] == 3
        assert check["_brand_rank"] == 2
        assert found == [
            _mention("hubspot.com", "HubSpot", "competitor", 1),
            _mention("pipedrive.com", "Pipedrive", "brand", 2),
        ]

    def test_cited_pages_rank_before_pages_only_read(self):
        content = [*_searched(FRESHWORKS, ZOHO), _text("Nothing named.", ZOHO)]
        check, *found = extract.reshape("checks", _payload(content))
        assert check["_sources"] == 2
        assert "_brand_rank" not in check
        assert [(m["_company"], m["_rank"]) for m in found] == [
            ("Zoho CRM", 1),
            ("Freshsales", 2),
        ]

    def test_a_page_cited_twice_and_read_once_counts_once(self):
        content = [
            *_searched(HUBSPOT, G2),
            _text("HubSpot is free.", HUBSPOT),
            _text("HubSpot scales.", HUBSPOT, G2),
        ]
        check = extract.reshape("checks", _payload(content))[0]
        assert check["_sources"] == 2

    def test_a_failed_search_contributes_no_pages(self):
        failed = {
            "type": "web_search_tool_result_error",
            "error_code": "max_uses_exceeded",
        }
        content = [_text("I'll search."), *_search(failed), _text("Pipedrive leads.")]
        check, *found = extract.reshape("checks", _payload(content))
        assert check["_sources"] == 0
        assert check["_brand_rank"] == 1
        assert [m["_company"] for m in found] == ["Pipedrive"]

    def test_an_answer_given_without_searching_is_a_check_with_no_sources(self):
        asked = "Could you clarify what you are looking for in a CRM?"
        payload = _payload([_text(asked)])
        assert extract.reshape("checks", payload) == [_check(payload, asked, 0)]

    def test_the_brand_rank_is_absent_when_the_brand_is_neither_named_nor_cited(
        self,
    ):
        content = [*_searched(HUBSPOT), _text("HubSpot leads.", HUBSPOT)]
        check, *found = extract.reshape("checks", _payload(content))
        assert "_brand_rank" not in check
        assert check["_sources"] == 1
        assert [m["_role"] for m in found] == ["competitor"]

    def test_the_check_keeps_the_payload_and_the_mentions_do_not(self):
        payload = _payload(self.CONTENT)
        check, first, _second = extract.reshape("checks", payload)
        assert check["response"] == payload["response"]
        assert check["request"] == payload["request"]
        assert "response" not in first
        assert "request" not in first

    def test_blocks_citations_and_results_that_are_not_objects_do_not_raise(self):
        content = [
            "oops",
            {"type": "text", "text": 7},
            {"type": "text", "text": "HubSpot", "citations": "nope"},
            {
                "type": "text",
                "text": "and",
                "citations": [3, {"url": 5}, {"title": "no url"}, {"url": ""}],
            },
            {
                "type": "web_search_tool_result",
                "content": ["x", {"title": "no url"}, {"url": ""}, {"url": 9}],
            },
            {"type": "web_search_tool_result"},
            {"type": "image"},
        ]
        check, *found = extract.reshape("checks", _payload(content))
        assert check["_answer"] == "HubSpot\nand"
        assert check["_sources"] == 0
        assert [m["_company"] for m in found] == ["HubSpot"]

    def test_a_response_that_is_not_a_message_is_an_empty_check(self):
        payload = {"request": _request(), "response": "gone"}
        assert extract.reshape("checks", payload) == [_check(payload, "", 0)]

    def test_a_payload_with_nothing_in_it_still_yields_a_check(self):
        assert extract.reshape("checks", {}) == [
            {
                "_source_id": "claude||",
                "_engine": "claude",
                "_query": "",
                "_checked_at": "",
                "_answer": "",
                "_sources": 0,
            }
        ]

    def test_the_stored_payload_is_not_mutated(self):
        payload = _payload(self.CONTENT)
        extract.reshape("checks", payload)
        assert payload == _payload(self.CONTENT)


class TestOtherObjectTypes:
    def test_an_unknown_object_type_passes_through(self):
        payload = {"request": _request(), "models": []}
        assert extract.reshape("models", payload) == [payload]


class TestTheObservationPath:
    def test_a_check_observes_the_day_the_query_was_asked(self):
        assert registry.get("claude").OBSERVED_AT == {"checks": "request.checked_at"}

    def test_the_check_day_is_the_provider_observation(self):
        module = registry.get("claude")
        payload = {"request": _request()}
        observed, which = observed_at_for(module, "checks", payload, INGESTED)
        assert which == "provider"
        assert observed == datetime(2026, 9, 4, tzinfo=UTC)


class TestCredentials:
    def test_the_stand_in_is_anthropic_behind_the_mock_with_the_mock_key(self):
        found = creds.credentials_for("claude")
        assert found.base_url == f"{settings.MOCK_BASE_URL}/anthropic"
        assert found.headers == {
            "x-api-key": "mock_anthropic_key",
            "anthropic-version": "2023-06-01",
        }
        assert found.params == {}
        assert found.auth is None
        assert found.real is False

    def test_the_real_key_travels_in_the_x_api_key_header(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-test-0000")
        found = creds.credentials_for("claude")
        assert found.base_url == "https://api.anthropic.com"
        assert found.headers == {
            "x-api-key": "anthropic-test-0000",
            "anthropic-version": "2023-06-01",
        }
        assert found.params == {}
        assert found.auth is None
        assert found.real is True


class TestCatalog:
    def test_claude_is_listed_under_spy(self):
        assert catalog.entry("claude") == {
            "source": "claude",
            "label": "Claude",
            "category": "Spy",
            "unlocks": "Brand and competitor mentions, cited sources",
        }


class TestTheMockFixture:
    @staticmethod
    def _rows():
        return json.loads((FIXTURES / "checks.json").read_text())

    def test_every_tracked_query_was_asked_once_on_the_anchor_day(self):
        rows = self._rows()
        assert [row["payload"]["request"]["query"] for row in rows] == list(
            spy.definition().queries
        )
        assert [row["source_id"] for row in rows] == [
            f"{spy.slug(query)}|{TODAY}" for query in spy.definition().queries
        ]

    def test_every_answer_searched_once_and_cited_pages_it_read(self):
        for row in self._rows():
            content = row["payload"]["response"]["content"]
            results = [b for b in content if b["type"] == "web_search_tool_result"]
            assert len(results) == 1
            read = {result["url"] for result in results[0]["content"]}
            cited = {c["url"] for b in content for c in b.get("citations", [])}
            assert cited
            assert cited <= read
