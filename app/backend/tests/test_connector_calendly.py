import importlib
import sys
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.sources import client
from app.sources.paginators import PAGINATORS

ADVERSARIAL_ROOT = "/adversarial"
MOCK_USER_URI = "https://api.calendly.com/users/abc123def456"
RESOLVED_USER_URI = "https://api.calendly.com/users/RESOLVED-0000"
CONFIGURED_USER_URI = "https://api.calendly.com/users/CONFIGURED-0000"
CALENDLY_TOKEN = "calendly-token-test-0000"
SCOPE_MESSAGE = "At least one of organization, group or user must be filled"
LIVE_PAGINATION_KEYS = {
    "count",
    "next_page",
    "next_page_token",
    "previous_page",
    "previous_page_token",
}


@pytest.fixture(autouse=True)
def without_ambient_credentials(monkeypatch):
    for name in ("CALENDLY_ACCESS_TOKEN", "CALENDLY_USER_URI", "CALENDLY_BASE_URL"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def calendly():
    return importlib.import_module("app.sources.calendly.connector")


def an_event(uuid="evt_001"):
    return {
        "uri": f"https://api.calendly.com/scheduled_events/{uuid}",
        "name": "30 Minute Demo",
        "status": "active",
        "start_time": "2026-06-05T14:00:00.000000Z",
        "end_time": "2026-06-05T14:30:00.000000Z",
        "event_memberships": [{"user_email": "jane@acme.io"}],
    }


def an_invitee(email="mike@globex.com"):
    return {
        "uri": "https://api.calendly.com/scheduled_events/evt_001/invitees/inv_001",
        "email": email,
        "name": "Mike Chen",
        "status": "active",
    }


def a_page(records):
    return {
        "collection": records,
        "pagination": {
            "count": len(records),
            "next_page": None,
            "next_page_token": None,
            "previous_page": None,
            "previous_page_token": None,
        },
    }


@pytest.fixture
def calendly_api(monkeypatch):
    seen = []

    def _install(*, events=None, invitees=None, me=None, invitees_status=200):
        def handler(request):
            seen.append(request)
            if request.url.path == "/users/me":
                return httpx.Response(200, json=me if me is not None else {})
            if request.url.path.endswith("/invitees"):
                if invitees_status != 200:
                    return httpx.Response(
                        invitees_status,
                        json={"title": "Resource Not Found"},
                    )
                return httpx.Response(200, json=a_page(invitees or []))
            return httpx.Response(
                200, json=a_page([an_event()] if events is None else events)
            )

        monkeypatch.setattr(client, "_transport", httpx.MockTransport(handler))
        return seen

    yield _install
    monkeypatch.setattr(client, "_transport", None)


@pytest.fixture
def collect():
    stored = []

    async def store(session, **kwargs):
        stored.append(kwargs)

    return store, stored


def a_resource(uri):
    return {"resource": {"uri": uri, "email": "jane@acme.io", "name": "Jane Smith"}}


def events_request(seen):
    return next(r for r in seen if r.url.path == "/scheduled_events")


class TestTheScopeTheRealApiDemands:
    async def test_the_events_request_names_the_user_it_is_scoped_to(
        self, calendly, calendly_api, collect
    ):
        seen = calendly_api(me=a_resource(RESOLVED_USER_URI))
        store, _stored = collect

        await calendly.pull(None, store)

        assert events_request(seen).url.params.get("user") == RESOLVED_USER_URI

    async def test_the_user_is_resolved_from_users_me_when_none_is_configured(
        self, calendly, calendly_api, collect
    ):
        seen = calendly_api(me=a_resource(RESOLVED_USER_URI))
        store, _stored = collect

        await calendly.pull(None, store)

        assert [r.url.path for r in seen][:2] == ["/users/me", "/scheduled_events"]

    async def test_a_configured_user_is_used_without_asking_users_me(
        self, calendly, calendly_api, collect, monkeypatch
    ):
        monkeypatch.setenv("CALENDLY_ACCESS_TOKEN", CALENDLY_TOKEN)
        monkeypatch.setenv("CALENDLY_USER_URI", CONFIGURED_USER_URI)
        seen = calendly_api(me=a_resource(RESOLVED_USER_URI))
        store, _stored = collect

        await calendly.pull(None, store)

        assert "/users/me" not in [r.url.path for r in seen]
        assert events_request(seen).url.params.get("user") == CONFIGURED_USER_URI

    async def test_a_users_me_without_a_resource_leaves_the_scope_empty(
        self, calendly, calendly_api, collect
    ):
        seen = calendly_api(me={})
        store, _stored = collect

        await calendly.pull(None, store)

        assert events_request(seen).url.params.get("user") == ""


class TestTheInviteeIsTheAttendee:
    async def test_each_event_carries_the_invitees_it_was_booked_by(
        self, calendly, calendly_api, collect
    ):
        calendly_api(me=a_resource(RESOLVED_USER_URI), invitees=[an_invitee()])
        store, stored = collect

        await calendly.pull(None, store)

        assert [i["email"] for i in stored[0]["raw_payload"]["_invitees"]] == [
            "mike@globex.com"
        ]

    async def test_the_invitees_are_asked_for_by_the_event_uuid(
        self, calendly, calendly_api, collect
    ):
        seen = calendly_api(me=a_resource(RESOLVED_USER_URI), invitees=[an_invitee()])
        store, _stored = collect

        await calendly.pull(None, store)

        assert [r.url.path for r in seen][-1] == "/scheduled_events/evt_001/invitees"

    async def test_an_event_without_a_uuid_asks_for_no_invitees(
        self, calendly, calendly_api, collect
    ):
        seen = calendly_api(me=a_resource(RESOLVED_USER_URI), events=[{}])
        store, stored = collect

        notes = await calendly.pull(None, store)

        assert stored == []
        assert notes == {"missing_id": 1}
        assert [r.url.path for r in seen] == ["/users/me", "/scheduled_events"]

    async def test_invitees_that_cannot_be_read_are_counted_not_fatal(
        self, calendly, calendly_api, collect
    ):
        calendly_api(me=a_resource(RESOLVED_USER_URI), invitees_status=404)
        store, stored = collect

        notes = await calendly.pull(None, store)

        assert notes == {"invitees_fetch_failed": 1}
        assert "_invitees" not in stored[0]["raw_payload"]


class TestTheMockDemandsTheScopeTheRealApiDemands:
    @pytest.fixture(scope="class")
    def mock_api(self):
        provider = Path(f"{ADVERSARIAL_ROOT}/seeds/providers/calendly.py")
        if not provider.is_file():
            pytest.skip("the mock providers are not mounted at /adversarial")
        if ADVERSARIAL_ROOT not in sys.path:
            sys.path.insert(0, ADVERSARIAL_ROOT)
        app = FastAPI()
        app.include_router(
            importlib.import_module("seeds.providers.calendly").router,
            prefix="/calendly",
        )
        return TestClient(app, headers={"Authorization": "Bearer mock_calendly_token"})

    def test_events_without_a_scope_are_refused(self, mock_api):
        assert mock_api.get("/calendly/scheduled_events?count=2").status_code == 400

    def test_the_refusal_reads_like_the_real_one(self, mock_api):
        body = mock_api.get("/calendly/scheduled_events?count=2").json()
        assert body["title"] == "Invalid Argument"
        assert body["message"] == "The supplied parameters are invalid."
        assert body["details"] == [
            {"message": SCOPE_MESSAGE, "parameter": "organization"},
            {"message": SCOPE_MESSAGE, "parameter": "user"},
            {"message": SCOPE_MESSAGE, "parameter": "group"},
        ]

    def test_a_named_user_is_answered(self, mock_api):
        answer = mock_api.get(
            "/calendly/scheduled_events", params={"user": MOCK_USER_URI, "count": 2}
        )
        assert answer.status_code == 200
        assert len(answer.json()["collection"]) == 2

    def test_a_named_organization_is_answered(self, mock_api):
        answer = mock_api.get(
            "/calendly/scheduled_events",
            params={"organization": "https://api.calendly.com/organizations/org789"},
        )
        assert answer.status_code == 200

    def test_the_pagination_block_carries_the_keys_the_live_one_does(self, mock_api):
        answer = mock_api.get(
            "/calendly/scheduled_events", params={"user": MOCK_USER_URI, "count": 2}
        )
        assert set(answer.json()["pagination"]) == LIVE_PAGINATION_KEYS

    def test_every_event_the_mock_lists_has_the_invitees_it_counts(self, mock_api):
        events = mock_api.get(
            "/calendly/scheduled_events", params={"user": MOCK_USER_URI, "count": 100}
        ).json()["collection"]
        counted = {
            e["uri"].rsplit("/", 1)[-1]: e["invitees_counter"]["total"] for e in events
        }
        listed = {
            uuid: len(
                mock_api.get(f"/calendly/scheduled_events/{uuid}/invitees").json()[
                    "collection"
                ]
            )
            for uuid in counted
        }
        assert listed == counted


class TestThePaginatorReadsTheLiveEnvelope:
    def test_the_next_token_is_read_from_the_key_the_live_envelope_carries(self):
        paginator = PAGINATORS["token_calendly"]
        pagination = dict.fromkeys(LIVE_PAGINATION_KEYS)
        pagination["next_page_token"] = "sEjwKmR2b3c"
        assert paginator.next_params({"pagination": pagination}, {"count": 2}) == {
            "count": 2,
            "page_token": "sEjwKmR2b3c",
        }

    def test_a_live_envelope_without_a_next_token_ends_the_walk(self):
        paginator = PAGINATORS["token_calendly"]
        pagination = dict.fromkeys(LIVE_PAGINATION_KEYS)
        pagination["count"] = 0
        assert paginator.next_params({"pagination": pagination}, {"count": 2}) is None
