import json
from datetime import UTC, datetime

import httpx
import pytest

from app.config import settings
from app.engine import checks, spy
from app.engine.pipeline import observed_at_for
from app.sources import catalog, client, creds, registry
from app.sources.google_serp import extract

FIXTURES = checks.REAL_FIXTURES.parent / "mock" / "google_serp"
INGESTED = datetime(2026, 9, 14, tzinfo=UTC)
TODAY = "2026-09-04"
QUERY = "best crm for small business"
SLUG = "best-crm-for-small-business"
TOKEN = "cmVhbGx5LWEtdG9rZW4="
UNAVAILABLE = "Can't generate an AI overview right now. Try again later."


def _result(position, link):
    return {
        "position": position,
        "title": f"Result {position}",
        "link": link,
        "displayed_link": link,
        "snippet": "A page about CRMs.",
        "source": "Site",
    }


def _search(results=(), overview=None):
    body = {
        "search_metadata": {"status": "Success"},
        "search_parameters": {"engine": "google", "q": QUERY},
        "organic_results": list(results),
    }
    if overview is not None:
        body["ai_overview"] = overview
    return body


def _overview(blocks, references=()):
    return {"text_blocks": list(blocks), "references": list(references)}


def _paragraph(text):
    return {"type": "paragraph", "snippet": text}


def _reference(link, index=0):
    return {"link": link, "source": spy.host(link), "index": index}


def _answering(search, fetched=None):
    def answer(request):
        params = request.url.params
        if params.get("engine") != "google_ai_overview":
            return search
        body = {
            "search_metadata": {"status": "Success"},
            "search_parameters": {
                "engine": "google_ai_overview",
                "page_token": params.get("page_token"),
            },
        }
        if fetched is not None:
            body["ai_overview"] = fetched
        return body

    return answer


def _request(engine, query=QUERY):
    return {
        "engine": engine,
        "query": query,
        "checked_at": TODAY,
        "country": "US",
        "language": "en",
    }


def _search_payload(results=()):
    return {"request": _request("google"), "response": _search(results)}


def _overview_payload(blocks, references=(), query=QUERY):
    return {
        "request": _request("ai_overview", query),
        "ai_overview": _overview(blocks, references),
    }


def _mention(engine, domain, name, role, rank, query=QUERY):
    return {
        "_source_id": f"{engine}|{spy.slug(query)}|{TODAY}|{domain}",
        "_mention_engine": engine,
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

        def _install(answer):
            def handler(request):
                seen.append(request)
                return httpx.Response(200, json=answer(request))

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
        return await registry.get("google_serp").pull(None, store)

    @staticmethod
    def _of(stored, object_type):
        return [s for s in stored if s["object_type"] == object_type]


class TestWhatTheConnectorAsksFor(_Capture):
    async def test_every_query_is_asked_in_the_definitions_country_and_language(
        self, capture, store
    ):
        seen = capture(_answering(_search()))
        await self._pull(store)
        spec = spy.definition()
        assert [r.url.params["q"] for r in seen] == list(spec.queries)
        for request in seen:
            assert request.method == "GET"
            assert request.url.path == "/search.json"
            assert request.url.params["engine"] == "google"
            assert request.url.params["gl"] == spec.country.lower()
            assert request.url.params["hl"] == spec.language
            assert request.url.params["num"] == "10"
            assert request.url.params["api_key"] == "mock_serpapi_key"

    async def test_every_search_is_stored_under_its_slug_and_the_day(
        self, capture, store, stored
    ):
        body = _search([_result(1, "https://www.zoho.com/crm/")])
        capture(_answering(body))
        await self._pull(store)
        spec = spy.definition()
        searches = self._of(stored, "searches")
        assert [s["source_id"] for s in searches] == [
            f"{spy.slug(q)}|{TODAY}" for q in spec.queries
        ]
        assert searches[0]["source"] == "google_serp"
        assert searches[0]["raw_payload"] == {
            "request": _request("google", spec.queries[0]),
            "response": body,
        }

    async def test_a_deferred_overview_is_fetched_through_its_token_at_once(
        self, capture, store, stored
    ):
        block = _overview([_paragraph("Pipedrive leads.")])
        deferred = {"page_token": TOKEN, "serpapi_link": "https://serpapi.com/x"}
        seen = capture(_answering(_search(overview=deferred), block))
        notes = await self._pull(store)
        engines = [r.url.params["engine"] for r in seen]
        assert engines == ["google", "google_ai_overview"] * 8
        follow_ups = [r for r in seen if r.url.params["engine"] == "google_ai_overview"]
        assert {r.url.params["page_token"] for r in follow_ups} == {TOKEN}
        assert all(r.url.params["api_key"] == "mock_serpapi_key" for r in follow_ups)
        overviews = self._of(stored, "ai_overviews")
        assert [o["source_id"] for o in overviews] == [
            s["source_id"] for s in self._of(stored, "searches")
        ]
        assert overviews[0]["raw_payload"] == {
            "request": _request("ai_overview", spy.definition().queries[0]),
            "ai_overview": block,
        }
        assert notes == {"ai_overview_fetched": 8}

    async def test_an_inline_overview_is_stored_without_a_second_request(
        self, capture, store, stored
    ):
        block = _overview([_paragraph("Pipedrive leads.")])
        seen = capture(_answering(_search(overview=block)))
        notes = await self._pull(store)
        assert len(seen) == 8
        overviews = self._of(stored, "ai_overviews")
        assert len(overviews) == 8
        assert overviews[0]["raw_payload"]["ai_overview"] == block
        assert notes is None

    async def test_an_overview_google_could_not_generate_is_counted_not_stored(
        self, capture, store, stored
    ):
        capture(_answering(_search(overview={"error": UNAVAILABLE})))
        notes = await self._pull(store)
        assert self._of(stored, "ai_overviews") == []
        assert notes == {"ai_overview_errors": 8}

    async def test_a_search_without_an_overview_is_counted(
        self, capture, store, stored
    ):
        capture(_answering(_search()))
        notes = await self._pull(store)
        assert self._of(stored, "ai_overviews") == []
        assert notes == {"ai_overview_absent": 8}

    async def test_a_block_with_neither_text_nor_error_is_absent(
        self, capture, store, stored
    ):
        capture(_answering(_search(overview={})))
        notes = await self._pull(store)
        assert self._of(stored, "ai_overviews") == []
        assert notes == {"ai_overview_absent": 8}

    async def test_a_fetched_overview_that_fails_is_counted_as_both(
        self, capture, store, stored
    ):
        deferred = {"page_token": TOKEN}
        capture(_answering(_search(overview=deferred), {"error": UNAVAILABLE}))
        notes = await self._pull(store)
        assert self._of(stored, "ai_overviews") == []
        assert notes == {"ai_overview_fetched": 8, "ai_overview_errors": 8}

    async def test_a_fetched_answer_without_a_block_is_absent(
        self, capture, store, stored
    ):
        capture(_answering(_search(overview={"page_token": TOKEN})))
        notes = await self._pull(store)
        assert self._of(stored, "ai_overviews") == []
        assert notes == {"ai_overview_fetched": 8, "ai_overview_absent": 8}


class TestTheSearchHook:
    RESULTS = (
        _result(1, "https://www.zoho.com/crm/"),
        _result(2, "https://www.g2.com/categories/crm"),
        _result(3, "https://www.pipedrive.com/en/features"),
        _result(4, "https://blog.zoho.com/crm/tips"),
    )

    def test_one_check_then_one_mention_per_company_on_the_page(self):
        check, *found = extract.reshape("searches", _search_payload(self.RESULTS))
        assert check["_source_id"] == f"google|{SLUG}|{TODAY}"
        assert check["_engine"] == "google"
        assert check["_query"] == QUERY
        assert check["_checked_at"] == TODAY
        assert check["_sources"] == 4
        assert check["_brand_rank"] == 3
        assert "_answer" not in check
        assert found == [
            _mention("google", "zoho.com", "Zoho CRM", "competitor", 1),
            _mention("google", "pipedrive.com", "Pipedrive", "brand", 3),
        ]

    def test_the_check_keeps_the_payload_and_the_mentions_do_not(self):
        payload = _search_payload(self.RESULTS)
        check, first, _second = extract.reshape("searches", payload)
        assert check["response"] == payload["response"]
        assert check["request"] == payload["request"]
        assert "response" not in first
        assert "request" not in first

    def test_the_brand_rank_is_absent_when_the_brand_is_not_on_the_page(self):
        results = [_result(1, "https://www.hubspot.com/products/crm")]
        check, *found = extract.reshape("searches", _search_payload(results))
        assert "_brand_rank" not in check
        assert [m["_company"] for m in found] == ["HubSpot"]

    def test_results_without_a_position_or_a_link_do_not_raise(self):
        payload = _search_payload(
            [
                "oops",
                {"link": "https://www.zoho.com/crm/"},
                {"position": "1", "link": "https://www.hubspot.com/"},
                {"position": 2},
            ]
        )
        check, *found = extract.reshape("searches", payload)
        assert check["_sources"] == 4
        assert found == []

    def test_a_payload_with_nothing_in_it_still_yields_a_check(self):
        assert extract.reshape("searches", {}) == [
            {
                "_source_id": "google||",
                "_engine": "google",
                "_query": "",
                "_checked_at": "",
                "_sources": 0,
            }
        ]

    def test_the_stored_payload_is_not_mutated(self):
        payload = _search_payload(self.RESULTS)
        extract.reshape("searches", payload)
        assert payload == _search_payload(self.RESULTS)


class TestTheOverviewHook:
    BLOCKS = (
        _paragraph("HubSpot and Pipedrive lead the shortlist."),
        {"type": "heading", "snippet": "Options"},
        {
            "type": "list",
            "list": [{"title": "Zoho CRM", "snippet": "Zoho CRM is the cheap one."}],
        },
    )

    def test_the_answer_is_every_snippet_joined_by_newlines(self):
        check = extract.reshape("ai_overviews", _overview_payload(self.BLOCKS))[0]
        assert check["_answer"] == (
            "HubSpot and Pipedrive lead the shortlist.\nOptions\nZoho CRM\n"
            "Zoho CRM is the cheap one."
        )
        assert check["_source_id"] == f"ai_overview|{SLUG}|{TODAY}"
        assert check["_engine"] == "ai_overview"
        assert check["_query"] == QUERY
        assert check["_checked_at"] == TODAY
        assert check["ai_overview"] == _overview(self.BLOCKS)

    def test_mentions_rank_by_where_the_name_first_appears(self):
        check, *found = extract.reshape("ai_overviews", _overview_payload(self.BLOCKS))
        assert check["_brand_rank"] == 2
        assert found == [
            _mention("ai_overview", "hubspot.com", "HubSpot", "competitor", 1),
            _mention("ai_overview", "pipedrive.com", "Pipedrive", "brand", 2),
            _mention("ai_overview", "zoho.com", "Zoho CRM", "competitor", 3),
        ]

    def test_a_company_only_cited_ranks_after_the_named_ones(self):
        payload = _overview_payload(
            [_paragraph("Pipedrive leads.")],
            [_reference("https://www.freshworks.com/crm/sales/")],
        )
        _check, *found = extract.reshape("ai_overviews", payload)
        assert [(m["_company"], m["_rank"]) for m in found] == [
            ("Pipedrive", 1),
            ("Freshsales", 2),
        ]

    def test_repeated_reference_links_count_once(self):
        same = "https://www.uschamber.com/co/start/strategy/low-cost-crm-tools"
        payload = _overview_payload(
            [_paragraph("Nothing named.")],
            [
                _reference(same, 0),
                _reference(same, 9),
                _reference("https://www.g2.com/categories/crm", 1),
            ],
        )
        check = extract.reshape("ai_overviews", payload)[0]
        assert check["_sources"] == 2

    def test_nested_lists_expandable_sections_and_tables_are_read(self):
        blocks = [
            {
                "type": "list",
                "list": [
                    {
                        "snippet": "Consider:",
                        "list": [{"snippet": "Freshsales for calling."}],
                    }
                ],
            },
            {
                "type": "expandable",
                "title": "More options",
                "text_blocks": [_paragraph("Zoho CRM is the cheap one.")],
            },
            {"type": "table", "table": [["Tool", "Price"], ["HubSpot", "$0"]]},
        ]
        check, *found = extract.reshape("ai_overviews", _overview_payload(blocks))
        assert check["_answer"] == (
            "Consider:\nFreshsales for calling.\nMore options\n"
            "Zoho CRM is the cheap one.\nTool | Price\nHubSpot | $0"
        )
        assert [(m["_company"], m["_rank"]) for m in found] == [
            ("Freshsales", 1),
            ("Zoho CRM", 2),
            ("HubSpot", 3),
        ]

    def test_blocks_and_references_that_are_not_objects_are_skipped(self):
        blocks = [
            "oops",
            3,
            {"type": "list", "list": "nope"},
            {"type": "table", "table": [["HubSpot"], "row"]},
            {"snippet": "   "},
            {"snippet": 7},
        ]
        references = [{"link": 5}, "x", {"title": "no link"}, {"link": ""}]
        check, *found = extract.reshape(
            "ai_overviews", _overview_payload(blocks, references)
        )
        assert check["_answer"] == "HubSpot"
        assert check["_sources"] == 0
        assert [m["_company"] for m in found] == ["HubSpot"]

    def test_an_overview_that_is_not_a_block_is_an_empty_check(self):
        payload = {"request": _request("ai_overview"), "ai_overview": "gone"}
        assert extract.reshape("ai_overviews", payload) == [
            {
                **payload,
                "_source_id": f"ai_overview|{SLUG}|{TODAY}",
                "_engine": "ai_overview",
                "_query": QUERY,
                "_checked_at": TODAY,
                "_answer": "",
                "_sources": 0,
            }
        ]

    def test_the_brand_rank_is_absent_when_the_brand_is_not_mentioned(self):
        payload = _overview_payload(
            [_paragraph("HubSpot leads.")],
            [_reference("https://www.hubspot.com/products/crm")],
        )
        check, *found = extract.reshape("ai_overviews", payload)
        assert "_brand_rank" not in check
        assert check["_sources"] == 1
        assert [m["_role"] for m in found] == ["competitor"]


class TestOtherObjectTypes:
    def test_an_unknown_object_type_passes_through(self):
        payload = {"request": _request("google"), "related_questions": []}
        assert extract.reshape("related_questions", payload) == [payload]


class TestTheObservationPath:
    def test_both_object_types_observe_the_day_the_query_was_asked(self):
        assert registry.get("google_serp").OBSERVED_AT == {
            "searches": "request.checked_at",
            "ai_overviews": "request.checked_at",
        }

    @pytest.mark.parametrize("object_type", ["searches", "ai_overviews"])
    def test_the_check_day_is_the_provider_observation(self, object_type):
        module = registry.get("google_serp")
        payload = {"request": _request("google")}
        observed, which = observed_at_for(module, object_type, payload, INGESTED)
        assert which == "provider"
        assert observed == datetime(2026, 9, 4, tzinfo=UTC)


class TestCredentials:
    def test_the_stand_in_is_serpapi_behind_the_mock_with_the_mock_key(self):
        found = creds.credentials_for("google_serp")
        assert found.base_url == f"{settings.MOCK_BASE_URL}/serpapi"
        assert found.params == {"api_key": "mock_serpapi_key"}
        assert found.headers == {}
        assert found.auth is None
        assert found.real is False

    def test_the_real_key_travels_as_the_api_key_parameter(self, monkeypatch):
        monkeypatch.setenv("SERPAPI_API_KEY", "serp-test-0000")
        found = creds.credentials_for("google_serp")
        assert found.base_url == "https://serpapi.com"
        assert found.params == {"api_key": "serp-test-0000"}
        assert found.headers == {}
        assert found.real is True


class TestCatalog:
    def test_google_search_is_listed_under_spy(self):
        assert catalog.entry("google_serp") == {
            "source": "google_serp",
            "label": "Google Search",
            "category": "Spy",
            "unlocks": "Brand rank, AI Overview mentions",
        }


class TestTheMockFixture:
    @staticmethod
    def _rows(name):
        return json.loads((FIXTURES / f"{name}.json").read_text())

    def test_every_tracked_query_was_searched_once(self):
        queries = [row["payload"]["request"]["query"] for row in self._rows("searches")]
        assert queries == list(spy.definition().queries)

    def test_every_search_carries_ten_organic_results(self):
        for row in self._rows("searches"):
            assert len(row["payload"]["response"]["organic_results"]) == 10

    def test_every_stored_overview_carries_text_blocks_and_references(self):
        rows = self._rows("ai_overviews")
        assert rows
        for row in rows:
            block = row["payload"]["ai_overview"]
            assert block["text_blocks"]
            assert block["references"]
            assert "error" not in block

    def test_an_overview_shares_its_source_id_with_its_search(self):
        searched = {row["source_id"] for row in self._rows("searches")}
        for row in self._rows("ai_overviews"):
            assert row["source_id"] in searched
