import json
from datetime import UTC, datetime

import httpx
import pytest

from app import clock
from app.engine import checks
from app.engine.pipeline import observed_at_for
from app.sources import client, registry
from app.sources.util import window

FIXTURES = checks.REAL_FIXTURES.parent / "mock" / "mixpanel"
INGESTED = datetime(2026, 9, 14, tzinfo=UTC)

EXPORT = "/api/2.0/export"
LIVE_CONTENT_TYPE = "text/plain; charset=utf-8"
ENDED_EARLY = "terminated early"

SERVICE_ACCOUNT = "mixpanel-user-test-0000"
SERVICE_SECRET = "mixpanel-secret-test-0000"
PROJECT = "7654321"


def payloads(name):
    rows = json.loads((FIXTURES / f"{name}.json").read_text())
    return [row["payload"] for row in rows]


def ndjson(records):
    return "\n".join(json.dumps(record) for record in records)


class _Export:
    @pytest.fixture
    def capture(self, monkeypatch):
        seen = []

        def _install(body):
            def handler(request):
                seen.append(request)
                return httpx.Response(
                    200, text=body, headers={"content-type": LIVE_CONTENT_TYPE}
                )

            monkeypatch.setattr(client, "_transport", httpx.MockTransport(handler))
            return seen

        return _install

    @pytest.fixture
    def stored(self):
        return []

    @pytest.fixture
    def store(self, stored):
        async def _store(session, **kwargs):
            stored.append(kwargs)

        return _store

    @staticmethod
    def configured(monkeypatch):
        monkeypatch.setenv("MIXPANEL_SERVICE_ACCOUNT_USERNAME", SERVICE_ACCOUNT)
        monkeypatch.setenv("MIXPANEL_SERVICE_ACCOUNT_SECRET", SERVICE_SECRET)
        monkeypatch.setenv("MIXPANEL_PROJECT_ID", PROJECT)


class TestTheWindowMovesWithTheClock(_Export):
    async def test_the_export_asks_for_the_rolling_ninety_days(self, capture, store):
        seen = capture("")

        await registry.get("mixpanel").pull(None, store)

        since, until = window()
        assert (since, until) == ("2026-06-07", "2026-09-04")
        assert seen[0].url.params.get("from_date") == since
        assert seen[0].url.params.get("to_date") == until

    async def test_the_window_ends_on_today_not_on_a_past_fortnight(
        self, capture, store
    ):
        seen = capture("")

        await registry.get("mixpanel").pull(None, store)

        assert seen[0].url.params.get("to_date") == clock.now().date().isoformat()


class TestTheServiceAccountNamesItsProject(_Export):
    async def test_the_export_carries_the_project_id_on_the_wire(
        self, capture, store, monkeypatch
    ):
        self.configured(monkeypatch)
        seen = capture("")

        await registry.get("mixpanel").pull(None, store)

        assert seen[0].url.path == EXPORT
        assert seen[0].url.params.get("project_id") == PROJECT

    async def test_the_project_rides_beside_a_basic_auth_header(
        self, capture, store, monkeypatch
    ):
        self.configured(monkeypatch)
        seen = capture("")

        await registry.get("mixpanel").pull(None, store)

        assert seen[0].headers["authorization"].startswith("Basic ")
        assert SERVICE_SECRET not in str(seen[0].url)


class TestTheExportIsReadAsTextNotAsADocument(_Export):
    async def test_a_text_plain_body_becomes_one_row_per_line(
        self, capture, store, stored
    ):
        capture(ndjson(payloads("events")))

        notes = await registry.get("mixpanel").pull(None, store)

        assert notes is None
        assert [s["source_id"] for s in stored] == [
            "mp_ev1",
            "mp_ev2",
            "mp_ev3",
            "mp_ev4",
        ]
        assert {s["object_type"] for s in stored} == {"events"}

    async def test_the_whole_line_is_kept_as_the_raw_payload(
        self, capture, store, stored
    ):
        capture(ndjson(payloads("events")))

        await registry.get("mixpanel").pull(None, store)

        assert [s["raw_payload"] for s in stored] == payloads("events")


class TestAnExportThatEndsEarly(_Export):
    def _with_sentinel(self):
        return f"{ndjson(payloads('events'))}\n{ENDED_EARLY}\n"

    async def test_the_sentinel_is_not_counted_as_a_malformed_line(
        self, capture, store
    ):
        capture(self._with_sentinel())

        notes = await registry.get("mixpanel").pull(None, store)

        assert notes is None

    async def test_the_rows_before_the_sentinel_are_kept(self, capture, store, stored):
        capture(self._with_sentinel())

        await registry.get("mixpanel").pull(None, store)

        assert len(stored) == len(payloads("events"))

    async def test_the_run_says_it_did_not_read_the_tail(self, capture, store):
        capture(f"{ENDED_EARLY}\n")

        with client.collect_stats() as stats:
            await registry.get("mixpanel").pull(None, store)

        assert stats.truncated
        assert any("early" in reason for reason in stats.truncation_reasons)

    async def test_a_body_of_nothing_but_the_sentinel_stores_nothing(
        self, capture, store, stored
    ):
        capture(f"{ENDED_EARLY}\n")

        await registry.get("mixpanel").pull(None, store)

        assert stored == []

    async def test_an_export_that_ran_to_the_end_claims_no_truncation(
        self, capture, store
    ):
        capture(ndjson(payloads("events")))

        with client.collect_stats() as stats:
            await registry.get("mixpanel").pull(None, store)

        assert not stats.truncated

    async def test_a_genuinely_malformed_line_is_still_counted(self, capture, store):
        capture('{"properties":{"$insert_id":"mp_ev1"}}\nnot json at all')

        notes = await registry.get("mixpanel").pull(None, store)

        assert notes == {"malformed_lines": 1}


class TestTheObservationPathNamesAFieldTheEventCarries:
    def test_the_connector_observes_the_event_time(self):
        assert registry.get("mixpanel").OBSERVED_AT == {"events": "properties.time"}

    def test_every_captured_event_dates_itself_from_the_provider(self):
        module = registry.get("mixpanel")
        for payload in payloads("events"):
            observed, which = observed_at_for(module, "events", payload, INGESTED)
            assert which == "provider"
            assert observed != INGESTED

    def test_every_captured_event_carries_the_insert_id_it_is_keyed_by(self):
        for payload in payloads("events"):
            assert payload["properties"]["$insert_id"]


class TestGeoPropertiesUseTheSpellingTheRawExportUses:
    def test_an_exported_event_names_its_country_mp_country_code(self):
        for payload in payloads("events"):
            assert "mp_country_code" in payload["properties"]

    def test_no_exported_event_uses_the_profile_spelling(self):
        for payload in payloads("events"):
            assert "$country_code" not in payload["properties"]

    def test_the_city_and_region_keep_the_dollar_prefix(self):
        for payload in payloads("events"):
            assert "$city" in payload["properties"]
            assert "$region" in payload["properties"]
