import httpx
import pytest

from app.sources import client
from app.sources.salesforce import connector as salesforce


@pytest.fixture
def route(monkeypatch):
    def _install(handler):
        monkeypatch.setattr(client, "_transport", httpx.MockTransport(handler))

    yield _install
    monkeypatch.setattr(client, "_transport", None)


@pytest.fixture
def collect():
    stored = []

    async def store(session, **kwargs):
        stored.append(kwargs)

    return store, stored


class TestSalesforceCursor:
    async def test_a_single_batch_needs_no_chaining(self, route, collect):
        store, stored = collect
        route(
            lambda request: httpx.Response(
                200, json={"done": True, "records": [{"Id": "a1"}]}
            )
        )
        await salesforce.pull(None, store)
        assert len(stored) == 3

    async def test_the_cursor_is_followed_until_the_server_says_done(
        self, route, collect
    ):
        store, stored = collect

        def handler(request):
            if "locator" in str(request.url):
                return httpx.Response(
                    200, json={"done": True, "records": [{"Id": "b"}]}
                )
            return httpx.Response(
                200,
                json={
                    "done": False,
                    "records": [{"Id": "a"}],
                    "nextRecordsUrl": "/services/data/v60.0/query/locator-01",
                },
            )

        route(handler)
        await salesforce.pull(None, store)
        assert [s["source_id"] for s in stored] == ["a", "b"] * 3

    async def test_the_chain_is_bounded_against_a_server_that_never_finishes(
        self, route, collect
    ):
        store, stored = collect
        route(
            lambda request: httpx.Response(
                200,
                json={
                    "done": False,
                    "records": [{"Id": "a"}],
                    "nextRecordsUrl": "/services/data/v60.0/query/locator-01",
                },
            )
        )
        await salesforce.pull(None, store)
        assert len(stored) == 101 * 3

    async def test_a_body_that_is_not_an_object_yields_no_records(self, route, collect):
        store, stored = collect
        route(lambda request: httpx.Response(200, json=["unexpected"]))
        await salesforce.pull(None, store)
        assert stored == []


class TestTheCursorGuardSaysSo:
    async def test_the_guard_marks_the_pull_truncated(self, route, collect):
        store, _stored = collect
        route(
            lambda request: httpx.Response(
                200,
                json={
                    "done": False,
                    "records": [{"Id": "a"}],
                    "nextRecordsUrl": "/services/data/v60.0/query/locator-01",
                },
            )
        )
        with client.collect_stats() as stats:
            await salesforce.pull(None, store)
        assert stats.truncated is True
        assert any("cursor guard" in r for r in stats.truncation_reasons)

    async def test_a_pull_the_server_finishes_is_not_truncated(self, route, collect):
        store, _stored = collect
        route(
            lambda request: httpx.Response(
                200, json={"done": True, "records": [{"Id": "a1"}]}
            )
        )
        with client.collect_stats() as stats:
            await salesforce.pull(None, store)
        assert stats.truncated is False


class TestWhatSalesforceAsksFor:
    async def test_three_soql_queries_walk_the_three_objects(self, route, collect):
        store, stored = collect
        seen = []

        def handler(request):
            seen.append(request)
            return httpx.Response(200, json={"done": True, "records": [{"Id": "a1"}]})

        route(handler)
        await salesforce.pull(None, store)

        assert [r.url.path for r in seen] == ["/query"] * 3
        froms = [r.url.params.get("q", "").rsplit("FROM ", 1)[-1] for r in seen]
        assert set(froms) == {"Account", "Contact", "Opportunity"}
        assert {(s["object_type"], s["source_id"]) for s in stored} == {
            ("accounts", "a1"),
            ("contacts", "a1"),
            ("opportunities", "a1"),
        }
