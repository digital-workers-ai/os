import json
from datetime import UTC, datetime

import httpx
import pytest

from app.engine import checks
from app.engine.pipeline import observed_at_for
from app.engine.transforms import normalize_currency
from app.sources import client, registry
from app.sources.paginators import TwilioPage
from tools.pull_source import key_types

FIXTURES = checks.REAL_FIXTURES.parent / "mock" / "twilio"
INGESTED = datetime(2026, 9, 14, tzinfo=UTC)

MESSAGES = "/2010-04-01/Accounts/AC0/Messages.json"

LIVE_ENVELOPE_KEYS = {
    "end",
    "first_page_uri",
    "messages",
    "next_page_uri",
    "page",
    "page_size",
    "previous_page_uri",
    "start",
    "uri",
}

DOCUMENTED_MESSAGE_KEY_TYPES = {
    "account_sid": {"string"},
    "api_version": {"string"},
    "body": {"string"},
    "date_created": {"string"},
    "date_sent": {"string"},
    "date_updated": {"string"},
    "direction": {"string"},
    "error_code": {"null"},
    "error_message": {"null"},
    "from": {"string"},
    "messaging_service_sid": {"string"},
    "num_media": {"string"},
    "num_segments": {"string"},
    "price": {"string"},
    "price_unit": {"string"},
    "sid": {"string"},
    "status": {"string"},
    "subresource_uris": {"object"},
    "subresource_uris.feedback": {"string"},
    "subresource_uris.media": {"string"},
    "to": {"string"},
    "uri": {"string"},
}


def payloads(name):
    rows = json.loads((FIXTURES / f"{name}.json").read_text())
    return [row["payload"] for row in rows]


def envelope(messages=(), *, page=0, next_page_uri=None):
    return {
        "end": page,
        "first_page_uri": f"{MESSAGES}?PageSize=1&Page=0",
        "messages": list(messages),
        "next_page_uri": next_page_uri,
        "page": page,
        "page_size": 1,
        "previous_page_uri": (
            None if page == 0 else f"{MESSAGES}?PageSize=1&Page={page - 1}"
        ),
        "start": page,
        "uri": f"{MESSAGES}?PageSize=1&Page={page}",
    }


class TestTheEnvelopeTheLiveAccountAnswersWith:
    def test_the_envelope_carries_exactly_the_keys_the_live_api_returned(self):
        assert set(envelope()) == LIVE_ENVELOPE_KEYS

    def test_there_is_no_next_page_token_field_to_read(self):
        assert "next_page_token" not in LIVE_ENVELOPE_KEYS

    def test_an_account_with_no_messages_still_answers_the_whole_envelope(self):
        assert set(envelope(next_page_uri=None)) == LIVE_ENVELOPE_KEYS
        assert envelope()["messages"] == []


class TestTheWalkFollowsNextPageUri:
    def test_the_query_the_vendor_sent_becomes_the_next_request(self):
        body = envelope(
            next_page_uri=f"{MESSAGES}?PageSize=1&Page=1&PageToken=PASM0001"
        )
        assert TwilioPage().next_params(body, {"PageSize": 1}) == {
            "PageSize": "1",
            "Page": "1",
            "PageToken": "PASM0001",
        }

    def test_the_token_is_the_vendors_own_never_an_empty_string(self):
        body = envelope(
            next_page_uri=f"{MESSAGES}?PageSize=1&Page=1&PageToken=PASM0001"
        )
        assert TwilioPage().next_params(body, {})["PageToken"] == "PASM0001"

    def test_an_account_with_no_messages_ends_the_walk_after_one_request(self):
        empty = envelope()
        assert TwilioPage().extract(empty) == []
        assert TwilioPage().next_params(empty, {"PageSize": 1}) is None

    def test_a_next_page_uri_with_no_query_ends_the_walk(self):
        assert TwilioPage().next_params(envelope(next_page_uri=MESSAGES), {}) is None


class TestTheConnectorWalksWhereTheEnvelopePoints:
    @pytest.fixture
    def capture(self, monkeypatch):
        seen = []

        def _install(pages):
            def handler(request):
                seen.append(request)
                page = int(request.url.params.get("Page", 0))
                return httpx.Response(200, json=pages[page])

            monkeypatch.setattr(client, "_transport", httpx.MockTransport(handler))
            return seen

        return _install

    @staticmethod
    def _two_pages():
        return [
            envelope(
                [{"sid": "SM0"}],
                next_page_uri=f"{MESSAGES}?PageSize=1&Page=1&PageToken=PASM0001",
            ),
            envelope([{"sid": "SM1"}], page=1),
        ]

    async def test_the_second_request_carries_the_token_off_next_page_uri(
        self, capture
    ):
        seen = capture(self._two_pages())

        async def store(session, **kwargs):
            pass

        await registry.get("twilio").pull(None, store)

        assert [r.url.params.get("PageToken") for r in seen] == [None, "PASM0001"]

    async def test_every_page_of_messages_is_stored_not_just_the_first(self, capture):
        capture(self._two_pages())
        stored = []

        async def store(session, **kwargs):
            stored.append(kwargs)

        await registry.get("twilio").pull(None, store)

        assert [s["source_id"] for s in stored] == ["SM0", "SM1"]

    async def test_an_empty_account_is_one_request_and_no_rows(self, capture):
        seen = capture([envelope()])
        stored = []

        async def store(session, **kwargs):
            stored.append(kwargs)

        notes = await registry.get("twilio").pull(None, store)

        assert len(seen) == 1
        assert stored == []
        assert notes is None


class TestTheMessageFixtureCarriesWhatTwilioDocuments:
    def test_every_key_and_type_is_one_the_message_resource_declares(self):
        assert key_types(payloads("messages")) == DOCUMENTED_MESSAGE_KEY_TYPES

    def test_each_message_carries_the_whole_record_not_a_subset(self):
        for payload in payloads("messages"):
            assert key_types([payload]) == DOCUMENTED_MESSAGE_KEY_TYPES

    def test_the_sid_the_connector_keys_on_is_always_present(self):
        assert all(p["sid"].startswith("SM") for p in payloads("messages"))


class TestTheObservationPathNamesAFieldTheRecordCarries:
    def test_the_connector_observes_the_update_stamp(self):
        assert registry.get("twilio").OBSERVED_AT == {"messages": "date_updated"}

    def test_every_message_dates_itself_from_the_provider(self):
        module = registry.get("twilio")
        for payload in payloads("messages"):
            observed, which = observed_at_for(module, "messages", payload, INGESTED)
            assert which == "provider"
            assert observed != INGESTED

    def test_the_rfc_2822_stamp_twilio_writes_is_understood(self):
        module = registry.get("twilio")
        payload = {"date_updated": "Mon, 14 Jul 2026 10:30:02 +0000"}
        observed, which = observed_at_for(module, "messages", payload, INGESTED)
        assert which == "provider"
        assert observed == datetime(2026, 7, 14, 10, 30, 2, tzinfo=UTC)


class TestThePriceUnitTwilioSends:
    def test_the_stand_in_speaks_the_uppercase_code_the_vendor_documents(self):
        assert {p["price_unit"] for p in payloads("messages")} == {"USD"}

    def test_either_casing_reaches_the_same_currency(self):
        upper = normalize_currency("twilio", "messages", "USD")
        lower = normalize_currency("twilio", "messages", "usd")
        assert upper == lower == "usd"
