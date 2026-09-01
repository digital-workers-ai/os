import httpx
import pytest

from app.config import settings
from app.sources import client
from app.sources.client import ConnectorError, SourceClient, redact_url
from app.sources.paginators import Paginator


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch):
    async def instant(_seconds):
        return None

    monkeypatch.setattr(client, "_sleep", instant)


@pytest.fixture
def transport(monkeypatch):
    def _install(handler):
        monkeypatch.setattr(client, "_transport", httpx.MockTransport(handler))

    yield _install
    monkeypatch.setattr(client, "_transport", None)


def responder(*responses):
    queue = list(responses)

    def handler(request):
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception):
            raise item
        return item

    return handler


def json_page(payload, status=200):
    return httpx.Response(status, json=payload)


class TestRedaction:
    def test_the_query_string_is_stripped(self):
        assert (
            redact_url("https://api.meta.com/v1/ads?access_token=SECRET")
            == "https://api.meta.com/v1/ads"
        )

    def test_a_url_with_no_query_is_unchanged(self):
        assert (
            redact_url("https://api.x.com/v1/things") == "https://api.x.com/v1/things"
        )

    def test_a_fragment_goes_too(self):
        assert "#" not in redact_url("https://api.x.com/v1?a=1#frag")


class TestConnectorError:
    def test_it_names_the_source_it_came_from(self):
        error = ConnectorError("hubspot", "HTTP 500")
        assert error.source == "hubspot"
        assert error.detail == "HTTP 500"
        assert str(error) == "[hubspot] HTTP 500"


class TestRetries:
    @pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
    async def test_a_retriable_status_is_retried_to_the_cap_then_named(
        self, transport, status
    ):
        attempts = {"n": 0}

        def handler(request):
            attempts["n"] += 1
            return httpx.Response(status)

        transport(handler)
        with pytest.raises(ConnectorError) as caught:
            await SourceClient("hubspot", "http://api").get("/x")
        assert attempts["n"] == client._MAX_ATTEMPTS
        assert f"HTTP {status}" in str(caught.value)
        assert "after 4 attempts" in str(caught.value)

    async def test_a_retry_that_succeeds_returns_the_good_page(self, transport):
        transport(responder(httpx.Response(503), json_page({"ok": True})))
        assert await SourceClient("hubspot", "http://api").get("/x") == {"ok": True}

    async def test_a_transport_error_is_retried_and_never_leaks_the_url(
        self, transport
    ):
        transport(responder(httpx.ConnectError("dns failure for ?token=SECRET")))
        with pytest.raises(ConnectorError) as caught:
            await SourceClient("hubspot", "http://api?token=SECRET").get("/x")
        assert "ConnectError" in str(caught.value)
        assert "SECRET" not in str(caught.value)

    @pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
    async def test_a_client_error_fails_immediately_rather_than_retrying(
        self, transport, status
    ):
        attempts = {"n": 0}

        def handler(request):
            attempts["n"] += 1
            return httpx.Response(status)

        transport(handler)
        with pytest.raises(ConnectorError, match=f"HTTP {status}"):
            await SourceClient("hubspot", "http://api").get("/x")
        assert attempts["n"] == 1

    async def test_no_error_message_carries_the_query_string(self, transport):
        transport(responder(httpx.Response(401)))
        with pytest.raises(ConnectorError) as caught:
            await SourceClient("meta", "http://api").get(
                "/ads", params={"access_token": "SECRET"}
            )
        assert "SECRET" not in str(caught.value)


class TestBodies:
    async def test_a_body_that_is_not_json_is_a_named_failure(self, transport):
        transport(responder(httpx.Response(200, text="<html>oops</html>")))
        with pytest.raises(ConnectorError, match="invalid JSON body"):
            await SourceClient("hubspot", "http://api").get("/x")


class TestPost:
    async def test_a_post_sends_its_json_and_parses_the_reply(self, transport):
        seen = {}

        def handler(request):
            seen["method"] = request.method
            seen["body"] = request.content
            return json_page({"created": True})

        transport(handler)
        result = await SourceClient("intercom", "http://api").post(
            "/search", json={"query": "x"}
        )
        assert result == {"created": True}
        assert seen["method"] == "POST"
        assert b"query" in seen["body"]

    async def test_a_post_with_a_bad_body_is_also_named(self, transport):
        transport(responder(httpx.Response(200, text="not json")))
        with pytest.raises(ConnectorError, match="invalid JSON body"):
            await SourceClient("intercom", "http://api").post(
                "/search", json={"query": "x"}
            )


class TestConstructorParams:
    async def test_the_default_params_ride_a_get(self, transport):
        seen = {}

        def handler(request):
            seen.update(request.url.params)
            return json_page({"ok": True})

        transport(handler)
        await SourceClient("meta", "http://api", params={"access_token": "T"}).get(
            "/ads", params={"limit": "5"}
        )
        assert seen == {"access_token": "T", "limit": "5"}

    async def test_the_default_params_ride_a_post(self, transport):
        seen = {}

        def handler(request):
            seen.update(request.url.params)
            return json_page({"ok": True})

        transport(handler)
        await SourceClient("meta", "http://api", params={"access_token": "T"}).post(
            "/search", json={"q": "x"}
        )
        assert seen == {"access_token": "T"}

    @pytest.mark.parametrize("method", ["get", "post", "get_text"])
    async def test_the_token_never_reaches_the_error(self, transport, method):
        transport(responder(httpx.Response(401)))
        source_client = SourceClient(
            "meta", "http://api", params={"access_token": "SECRET"}
        )
        calls = {
            "get": lambda: source_client.get("/ads"),
            "post": lambda: source_client.post("/search", json={}),
            "get_text": lambda: source_client.get_text("/export"),
        }
        with pytest.raises(ConnectorError) as caught:
            await calls[method]()
        assert "SECRET" not in str(caught.value)


class TestGetText:
    async def test_text_bodies_come_back_raw_for_ndjson_exports(self, transport):
        transport(responder(httpx.Response(200, text='{"a":1}\n{"a":2}')))
        body = await SourceClient("segment", "http://api").get_text("/export")
        assert body.count("\n") == 1

    async def test_an_oversized_export_is_truncated_and_says_so(
        self, transport, monkeypatch
    ):
        monkeypatch.setattr(settings, "CONNECTOR_MAX_BYTES", 64)
        transport(responder(httpx.Response(200, text="x" * 5000)))
        source_client = SourceClient("segment", "http://api")
        body = await source_client.get_text("/export")
        assert len(body) <= 64
        assert source_client.truncated is True
        assert any("byte cap" in r for r in source_client.truncation_reasons)

    async def test_an_export_inside_the_cap_is_untouched(self, transport, monkeypatch):
        monkeypatch.setattr(settings, "CONNECTOR_MAX_BYTES", 10_000)
        transport(responder(httpx.Response(200, text='{"a":1}\n{"a":2}')))
        source_client = SourceClient("segment", "http://api")
        body = await source_client.get_text("/export")
        assert body.count("\n") == 1
        assert source_client.truncated is False


class TestPagination:
    async def test_every_page_is_walked_and_concatenated(self, transport):
        transport(
            responder(
                json_page(
                    {"results": [{"id": 1}], "paging": {"next": {"after": "c1"}}}
                ),
                json_page({"results": [{"id": 2}]}),
            )
        )
        rows = await SourceClient("hubspot", "http://api").get(
            "/companies", paginate="cursor_hubspot"
        )
        assert [r["id"] for r in rows] == [1, 2]

    async def test_a_cursor_that_never_advances_is_halted(self, transport):
        transport(
            responder(
                json_page(
                    {"results": [{"id": 1}], "paging": {"next": {"after": "same"}}}
                )
            )
        )
        source_client = SourceClient("hubspot", "http://api")
        rows = await source_client.get("/companies", paginate="cursor_hubspot")
        assert source_client.truncated is True
        assert any("repeated cursor" in r for r in source_client.truncation_reasons)
        assert len(rows) >= 1

    async def test_the_page_cap_stops_the_walk_and_says_so(
        self, transport, monkeypatch
    ):
        monkeypatch.setattr(settings, "CONNECTOR_MAX_PAGES", 2)
        counter = {"n": 0}

        def handler(request):
            counter["n"] += 1
            return json_page(
                {
                    "results": [{"id": counter["n"]}],
                    "paging": {"next": {"after": f"c{counter['n']}"}},
                }
            )

        transport(handler)
        source_client = SourceClient("hubspot", "http://api")
        await source_client.get("/companies", paginate="cursor_hubspot")
        assert source_client.truncated is True
        assert any("page cap 2" in r for r in source_client.truncation_reasons)

    async def test_the_byte_cap_stops_the_walk_and_says_so(
        self, transport, monkeypatch
    ):
        monkeypatch.setattr(settings, "CONNECTOR_MAX_BYTES", 10)
        counter = {"n": 0}

        def handler(request):
            counter["n"] += 1
            return json_page(
                {
                    "results": [{"id": counter["n"], "pad": "x" * 50}],
                    "paging": {"next": {"after": f"c{counter['n']}"}},
                }
            )

        transport(handler)
        source_client = SourceClient("hubspot", "http://api")
        await source_client.get("/companies", paginate="cursor_hubspot")
        assert source_client.truncated is True
        assert any("byte cap" in r for r in source_client.truncation_reasons)

    async def test_a_failure_mid_walk_keeps_the_pages_already_fetched(self, transport):
        transport(
            responder(
                json_page(
                    {"results": [{"id": 1}], "paging": {"next": {"after": "c1"}}}
                ),
                httpx.Response(500),
            )
        )
        source_client = SourceClient("hubspot", "http://api")
        rows = await source_client.get("/companies", paginate="cursor_hubspot")
        assert [r["id"] for r in rows] == [1]
        assert source_client.truncated is True
        assert any("mid-pagination" in r for r in source_client.truncation_reasons)

    async def test_a_failure_on_the_very_first_page_still_raises(self, transport):
        transport(responder(httpx.Response(500)))
        with pytest.raises(ConnectorError):
            await SourceClient("hubspot", "http://api").get(
                "/companies", paginate="cursor_hubspot"
            )

    async def test_a_body_shaped_wrong_for_its_paginator_is_named(self, transport):
        transport(responder(json_page({"unexpected": "shape"})))
        with pytest.raises(ConnectorError):
            await SourceClient("hubspot", "http://api").get(
                "/companies", paginate="cursor_hubspot"
            )


class TestThePageCapIsPerWalk:
    async def test_a_second_endpoint_gets_its_own_budget(self, transport, monkeypatch):
        monkeypatch.setattr(settings, "CONNECTOR_MAX_PAGES", 2)
        paths = []

        def handler(request):
            paths.append(request.url.path)
            return json_page(
                {
                    "results": [{"id": len(paths)}],
                    "paging": {"next": {"after": f"c{len(paths)}"}},
                }
            )

        transport(handler)
        source_client = SourceClient("hubspot", "http://api")
        first = await source_client.get("/companies", paginate="cursor_hubspot")
        second = await source_client.get("/deals", paginate="cursor_hubspot")

        assert len(first) == 2
        assert len(second) == 2, "the second endpoint was starved by the first"
        assert "/deals" in paths, "no request was issued for the second endpoint"

    async def test_the_cap_still_bounds_one_hostile_walk(self, transport, monkeypatch):
        monkeypatch.setattr(settings, "CONNECTOR_MAX_PAGES", 3)
        counter = {"n": 0}

        def handler(request):
            counter["n"] += 1
            return json_page(
                {
                    "results": [{"id": counter["n"]}],
                    "paging": {"next": {"after": f"c{counter['n']}"}},
                }
            )

        transport(handler)
        source_client = SourceClient("hubspot", "http://api")
        rows = await source_client.get("/companies", paginate="cursor_hubspot")
        assert len(rows) == 3
        assert source_client.truncated is True

    async def test_pages_read_still_totals_the_whole_pull(self, transport, monkeypatch):
        monkeypatch.setattr(settings, "CONNECTOR_MAX_PAGES", 2)

        def handler(request):
            return json_page({"results": [{"id": 1}]})

        transport(handler)
        source_client = SourceClient("hubspot", "http://api")
        await source_client.get("/companies", paginate="cursor_hubspot")
        await source_client.get("/deals", paginate="cursor_hubspot")
        assert source_client.pages_read == 2


class TestStatsCollection:
    async def test_a_pull_aggregates_pages_across_every_client_it_made(self, transport):
        transport(responder(json_page({"ok": True})))
        with client.collect_stats() as stats:
            await SourceClient("hubspot", "http://api").get("/a")
            await SourceClient("stripe", "http://api").get("/b")
        assert stats.pages_read == 2
        assert stats.truncated is False
        assert stats.truncation_reasons == []

    async def test_truncation_anywhere_marks_the_whole_pull(self, transport):
        transport(
            responder(
                json_page(
                    {"results": [{"id": 1}], "paging": {"next": {"after": "same"}}}
                )
            )
        )
        with client.collect_stats() as stats:
            await SourceClient("hubspot", "http://api").get(
                "/companies", paginate="cursor_hubspot"
            )
        assert stats.truncated is True
        assert stats.truncation_reasons

    async def test_clients_built_outside_the_block_are_not_counted(self, transport):
        transport(responder(json_page({"ok": True})))
        outside = SourceClient("hubspot", "http://api")
        with client.collect_stats() as stats:
            pass
        await outside.get("/a")
        assert stats.pages_read == 0


class TestWithoutAnInstalledTransport:
    async def test_the_client_speaks_real_http(self):
        real = SourceClient("hubspot", "http://api")._client()
        assert isinstance(real._transport, httpx.AsyncHTTPTransport)
        await real.aclose()


class TestAuth:
    async def test_basic_auth_reaches_the_request(self, transport):
        seen = []

        def handler(request):
            seen.append(request)
            return json_page({"ok": True})

        transport(handler)
        await SourceClient("twilio", "http://api", auth=("u", "p")).get("/x")
        assert seen[0].headers["Authorization"] == "Basic dTpw"

    async def test_no_auth_pair_adds_no_authorization_header(self, transport):
        seen = []

        def handler(request):
            seen.append(request)
            return json_page({"ok": True})

        transport(handler)
        await SourceClient("hubspot", "http://api").get("/x")
        assert "authorization" not in seen[0].headers


class _HeaderPager(Paginator):
    def __init__(self):
        self.header_calls = 0

    def extract(self, data):
        return self._require_list(data, "items")

    def next_params(self, data, params):
        after = data.get("next")
        return {**params, "after": after} if after else None

    def next_from_headers(self, headers, params):
        self.header_calls += 1
        cursor = headers.get("X-Next")
        return {**params, "page": cursor} if cursor else None


class TestHeaderPagination:
    async def test_the_walk_continues_from_the_response_headers(self, transport):
        transport(
            responder(
                httpx.Response(
                    200, json={"items": [{"id": 1}]}, headers={"X-Next": "2"}
                ),
                json_page({"items": [{"id": 2}]}),
            )
        )
        rows = await SourceClient("shopify", "http://api").get(
            "/orders", paginate=_HeaderPager()
        )
        assert [r["id"] for r in rows] == [1, 2]

    async def test_headers_are_consulted_only_after_the_body_says_nothing(
        self, transport
    ):
        seen = []

        def handler(request):
            seen.append(dict(request.url.params))
            if len(seen) == 1:
                return httpx.Response(
                    200,
                    json={"items": [{"id": 1}], "next": "c1"},
                    headers={"X-Next": "ignored"},
                )
            return json_page({"items": [{"id": 2}]})

        transport(handler)
        pager = _HeaderPager()
        rows = await SourceClient("shopify", "http://api").get(
            "/orders", paginate=pager
        )
        assert [r["id"] for r in rows] == [1, 2]
        assert seen == [{}, {"after": "c1"}]
        assert pager.header_calls == 1


class TestPublicTruncate:
    async def test_truncate_feeds_the_truncation_reasons(self):
        source_client = SourceClient("salesforce", "http://api")
        source_client.truncate("salesforce cursor guard reached on accounts")
        assert source_client.truncated is True
        assert (
            "salesforce cursor guard reached on accounts"
            in source_client.truncation_reasons
        )

    async def test_a_public_truncate_is_visible_to_the_stats_collector(self):
        with client.collect_stats() as stats:
            SourceClient("salesforce", "http://api").truncate("stopped early")
        assert stats.truncated is True
        assert "stopped early" in stats.truncation_reasons
