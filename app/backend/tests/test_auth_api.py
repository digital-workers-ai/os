from datetime import timedelta
from functools import partial
from urllib.parse import parse_qs, parse_qsl, urlsplit

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select

from app import auth, mcp
from app.api import auth_api
from app.config import (
    AUTH_SIGNING_KEY_ENV,
    GOOGLE_CLIENT_ID_ENV,
    GOOGLE_CLIENT_SECRET_ENV,
    settings,
)
from app.db import get_session
from app.main import app
from app.models import ApiKey, McpCall, McpGrant
from tests.conftest import NOW

ANA = "ana@example.com"
BO = "bo@example.com"
NONCE = "nonce-1"
PUBLIC_URL = "http://localhost:8092"
GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
CALLBACK = f"{PUBLIC_URL}/api/auth/callback"
BROWSER_ONLY = {"detail": "manage access from a signed-in browser"}
MANAGEMENT = [
    ("GET", "/api/auth/keys", None),
    ("POST", "/api/auth/keys", {"label": "nightly"}),
    ("DELETE", "/api/auth/keys/1", None),
    ("GET", "/api/auth/clients", None),
    ("DELETE", "/api/auth/clients/1", None),
]


def _key(label: str, created_by: str = ANA, raw: str | None = None, **fields) -> ApiKey:
    raw = raw or auth.new_key()
    return ApiKey(
        key_hash=auth.hash_key(raw),
        prefix=raw[:8],
        label=label,
        created_by=created_by,
        **fields,
    )


@pytest_asyncio.fixture
async def api(session):
    async def override():
        yield session

    app.dependency_overrides[get_session] = override
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://backend"
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_on(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "AUTH_ALLOWED_EMAILS", ANA)
    monkeypatch.setattr(settings, "PUBLIC_URL", PUBLIC_URL)
    monkeypatch.setenv(GOOGLE_CLIENT_ID_ENV, "client-id")
    monkeypatch.setenv(GOOGLE_CLIENT_SECRET_ENV, "client-secret")
    monkeypatch.setenv(AUTH_SIGNING_KEY_ENV, "signing-key")


@pytest.fixture
def signed_in(api, auth_on):
    api.cookies.set(
        auth.SESSION_COOKIE,
        auth.sign_token({"email": ANA}, auth.SESSION_TTL_SECONDS),
    )
    return api


@pytest.fixture
def same_browser(api, auth_on):
    api.cookies.set(auth.OAUTH_STATE_COOKIE, NONCE)
    return api


@pytest_asyncio.fixture
async def keyed(api, auth_on, session, sessionmaker_for_test, monkeypatch):
    monkeypatch.setattr(auth, "async_session", sessionmaker_for_test)
    monkeypatch.setattr(mcp.server, "auth", auth.ApiKeys())
    raw = auth.new_key()
    session.add(_key("leaked", raw=raw))
    await session.commit()
    api.headers["Authorization"] = f"Bearer {raw}"
    return api


def _google(monkeypatch, token_status=200, userinfo_status=200, email=ANA):
    seen: list[httpx.Request] = []

    def handler(request):
        seen.append(request)
        if str(request.url) == auth_api.GOOGLE_TOKEN_URL:
            return httpx.Response(token_status, json={"access_token": "at-1"})
        return httpx.Response(userinfo_status, json={"email": email})

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        partial(httpx.AsyncClient, transport=httpx.MockTransport(handler)),
    )
    return seen


def _state(next_url: str, nonce: str = NONCE) -> str:
    return auth.sign_token({"next": next_url, "nonce": nonce}, 600)


def _set_cookies(response) -> dict[str, str]:
    return {
        header.split("=", 1)[0]: header
        for header in response.headers.get_list("set-cookie")
    }


def _forgets_the_state(response) -> None:
    header = _set_cookies(response)[auth.OAUTH_STATE_COOKIE]
    assert header.startswith(f'{auth.OAUTH_STATE_COOKIE}="";')
    assert "Max-Age=0" in header


class TestMe:
    async def test_with_auth_off_nobody_is_signed_in(self, api):
        assert (await api.get("/api/auth/me")).json() == {
            "auth": "open",
            "email": None,
        }

    async def test_with_auth_on_the_session_names_the_person(self, signed_in):
        assert (await signed_in.get("/api/auth/me")).json() == {
            "auth": "google",
            "email": ANA,
        }

    async def test_a_key_names_its_maker(self, keyed):
        assert (await keyed.get("/api/auth/me")).json() == {
            "auth": "google",
            "email": ANA,
        }


class TestLogin:
    async def test_it_sends_the_browser_to_google_and_remembers_the_attempt(
        self, api, auth_on
    ):
        response = await api.get("/api/auth/login", params={"next": "/insights"})
        assert response.status_code in (302, 307)
        location = urlsplit(response.headers["location"])
        assert location._replace(query="").geturl() == GOOGLE_AUTH
        query = dict(parse_qsl(location.query))
        state = auth.read_token(query.pop("state"))
        assert query == {
            "client_id": "client-id",
            "redirect_uri": CALLBACK,
            "response_type": "code",
            "scope": "openid email",
            "prompt": "select_account",
        }
        nonce = response.cookies[auth.OAUTH_STATE_COOKIE]
        assert state == {"next": f"{PUBLIC_URL}/insights", "nonce": nonce}
        assert len(nonce) == 22
        cookie = response.headers["set-cookie"]
        assert cookie.startswith(f"{auth.OAUTH_STATE_COOKIE}=")
        assert "Max-Age=600" in cookie
        assert "HttpOnly" in cookie
        assert "Path=/" in cookie

    @pytest.mark.parametrize(
        ("given", "kept"),
        [
            ("/insights?tab=goals", f"{PUBLIC_URL}/insights?tab=goals"),
            ("http://localhost:3000/insights", "http://localhost:3000/insights"),
            ("https://evil.example/insights", "/"),
            ("//evil.example/insights", "/"),
            ("///evil.example", "/"),
            ("////evil.example/x", "/"),
            ("/\\evil.example/insights", "/"),
            (None, f"{PUBLIC_URL}/"),
        ],
    )
    async def test_only_a_local_next_survives(self, api, auth_on, given, kept):
        params = {} if given is None else {"next": given}
        response = await api.get("/api/auth/login", params=params)
        query = parse_qs(urlsplit(response.headers["location"]).query)
        assert auth.read_token(query["state"][0])["next"] == kept

    async def test_with_auth_off_there_is_nowhere_to_go(self, api):
        response = await api.get("/api/auth/login")
        assert response.status_code == 409
        assert response.json() == {"detail": "AUTH_ENABLED is off"}


class TestCallback:
    async def test_an_allowed_address_gets_a_session_and_its_page(
        self, same_browser, monkeypatch
    ):
        seen = _google(monkeypatch)
        response = await same_browser.get(
            "/api/auth/callback", params={"code": "c-1", "state": _state("/insights")}
        )
        assert response.status_code in (302, 307)
        assert response.headers["location"] == "/insights"
        exchange, userinfo = seen
        assert exchange.method == "POST"
        assert str(exchange.url) == auth_api.GOOGLE_TOKEN_URL
        assert dict(parse_qsl(exchange.content.decode())) == {
            "code": "c-1",
            "client_id": "client-id",
            "client_secret": "client-secret",
            "redirect_uri": CALLBACK,
            "grant_type": "authorization_code",
        }
        assert userinfo.method == "GET"
        assert str(userinfo.url) == auth.USERINFO_URL
        assert userinfo.headers["authorization"] == "Bearer at-1"
        cookie = _set_cookies(response)[auth.SESSION_COOKIE]
        assert f"Max-Age={auth.SESSION_TTL_SECONDS}" in cookie
        assert "HttpOnly" in cookie
        assert "Path=/" in cookie
        assert auth.read_token(response.cookies[auth.SESSION_COOKIE])["email"] == ANA
        _forgets_the_state(response)

    @pytest.mark.parametrize(
        ("next_url", "denied"),
        [
            ("/insights", "/insights?login=denied"),
            ("/insights?tab=goals", "/insights?tab=goals&login=denied"),
        ],
    )
    async def test_a_stranger_is_sent_back_denied(
        self, same_browser, monkeypatch, next_url, denied
    ):
        _google(monkeypatch, email=BO)
        response = await same_browser.get(
            "/api/auth/callback", params={"code": "c-1", "state": _state(next_url)}
        )
        assert response.status_code in (302, 307)
        assert response.headers["location"] == denied
        assert list(_set_cookies(response)) == [auth.OAUTH_STATE_COOKIE]
        _forgets_the_state(response)

    @pytest.mark.parametrize("outcome", [{"error": "access_denied"}, {}])
    async def test_cancelling_at_google_goes_back_without_a_session(
        self, same_browser, monkeypatch, outcome
    ):
        seen = _google(monkeypatch)
        response = await same_browser.get(
            "/api/auth/callback", params={**outcome, "state": _state("/insights")}
        )
        assert response.status_code in (302, 307)
        assert response.headers["location"] == "/insights"
        assert list(_set_cookies(response)) == [auth.OAUTH_STATE_COOKIE]
        _forgets_the_state(response)
        assert seen == []

    async def test_a_state_nobody_signed_is_refused(self, same_browser, monkeypatch):
        seen = _google(monkeypatch)
        response = await same_browser.get(
            "/api/auth/callback", params={"code": "c-1", "state": "not-ours"}
        )
        assert response.status_code == 400
        assert response.json() == {"detail": "state was not issued by this server"}
        assert seen == []

    @pytest.mark.parametrize("held", [None, "another-browsers-nonce"])
    async def test_a_state_this_browser_did_not_start_is_refused(
        self, api, auth_on, monkeypatch, held
    ):
        if held is not None:
            api.cookies.set(auth.OAUTH_STATE_COOKIE, held)
        seen = _google(monkeypatch)
        response = await api.get(
            "/api/auth/callback", params={"code": "c-1", "state": _state("/insights")}
        )
        assert response.status_code == 400
        assert response.json() == {
            "detail": "sign-in state does not match this browser"
        }
        assert seen == []
        assert "set-cookie" not in response.headers

    async def test_a_code_google_refuses_is_refused(self, same_browser, monkeypatch):
        seen = _google(monkeypatch, token_status=400)
        response = await same_browser.get(
            "/api/auth/callback", params={"code": "c-1", "state": _state("/")}
        )
        assert response.status_code == 400
        assert response.json() == {"detail": "Google refused the code"}
        assert len(seen) == 1

    async def test_a_token_google_cannot_read_is_refused(
        self, same_browser, monkeypatch
    ):
        _google(monkeypatch, userinfo_status=401)
        response = await same_browser.get(
            "/api/auth/callback", params={"code": "c-1", "state": _state("/")}
        )
        assert response.status_code == 400
        assert response.json() == {"detail": "Google refused the token"}


class TestLogout:
    async def test_it_clears_the_session(self, api):
        response = await api.post("/api/auth/logout")
        assert response.status_code == 204
        assert response.content == b""
        cookie = response.headers["set-cookie"]
        assert cookie.startswith(f'{auth.SESSION_COOKIE}="";')
        assert "Max-Age=0" in cookie
        assert "Path=/" in cookie


class TestManagement:
    @pytest.mark.parametrize(("method", "path", "body"), MANAGEMENT)
    async def test_a_key_holder_is_refused(self, keyed, method, path, body):
        response = await keyed.request(method, path, json=body)
        assert response.status_code == 403
        assert response.json() == BROWSER_ONLY

    @pytest.mark.parametrize(("method", "path", "body"), MANAGEMENT)
    async def test_with_auth_off_there_is_no_browser_to_manage_from(
        self, api, method, path, body
    ):
        response = await api.request(method, path, json=body)
        assert response.status_code == 403
        assert response.json() == BROWSER_ONLY


class TestKeys:
    async def test_nothing_minted_is_an_empty_list(self, signed_in):
        assert (await signed_in.get("/api/auth/keys")).json() == []

    async def test_a_blank_label_is_refused(self, signed_in):
        response = await signed_in.post("/api/auth/keys", json={"label": "   "})
        assert response.status_code == 422

    async def test_minting_shows_the_raw_key_once_and_stores_its_hash(
        self, signed_in, session
    ):
        response = await signed_in.post(
            "/api/auth/keys", json={"label": "  nightly-sync  "}
        )
        assert response.status_code == 201
        body = response.json()
        raw = body.pop("key")
        assert raw.startswith("os_")
        assert body == {"seq": 1, "prefix": raw[:8], "label": "nightly-sync"}
        [row] = (await session.scalars(select(ApiKey))).all()
        assert row.key_hash == auth.hash_key(raw)
        assert row.prefix == raw[:8]
        assert row.created_by == ANA
        assert row.revoked_at is None
        listed = (await signed_in.get("/api/auth/keys")).json()
        assert listed == [
            {
                "seq": 1,
                "prefix": raw[:8],
                "label": "nightly-sync",
                "created_by": ANA,
                "created_at": row.created_at.isoformat(),
                "last_used_at": None,
            }
        ]

    async def test_the_list_is_live_keys_newest_first(self, signed_in, session):
        first = _key("first")
        used = _key("used", created_by=BO, last_used_at=NOW)
        revoked = _key("revoked", revoked_at=NOW)
        session.add_all([first, used, revoked])
        await session.commit()
        listed = (await signed_in.get("/api/auth/keys")).json()
        assert [(k["seq"], k["label"]) for k in listed] == [(2, "used"), (1, "first")]
        assert listed[0]["created_by"] == BO
        assert listed[0]["last_used_at"] == NOW.isoformat()
        assert listed[1]["last_used_at"] is None

    async def test_revoking_hides_the_key_and_happens_once(self, signed_in, session):
        key = _key("nightly")
        session.add(key)
        await session.commit()
        response = await signed_in.delete("/api/auth/keys/1")
        assert response.status_code == 204
        await session.refresh(key)
        assert key.revoked_at == NOW
        assert (await signed_in.get("/api/auth/keys")).json() == []
        assert (await signed_in.delete("/api/auth/keys/1")).status_code == 404
        assert (await signed_in.delete("/api/auth/keys/99")).status_code == 404


def _grant(client_id: str, **fields) -> McpGrant:
    return McpGrant(client_id=client_id, email=ANA, **fields)


class TestClients:
    async def test_the_list_is_live_grants_newest_first(self, signed_in, session):
        session.add_all(
            [
                _grant(
                    "client-a",
                    client_name="Claude Code",
                    redirect_uri="http://localhost:51234/callback",
                ),
                _grant("client-b", last_seen_at=NOW),
                _grant("client-c", client_name="gone", revoked_at=NOW),
            ]
        )
        await session.commit()
        rows = (await signed_in.get("/api/auth/clients")).json()
        created = [
            row.created_at
            for row in (
                await session.scalars(select(McpGrant).order_by(McpGrant.seq.desc()))
            ).all()
        ]
        assert rows == [
            {
                "seq": 2,
                "client_name": None,
                "redirect_uri": None,
                "email": ANA,
                "created_at": created[1].isoformat(),
                "last_seen_at": NOW.isoformat(),
            },
            {
                "seq": 1,
                "client_name": "Claude Code",
                "redirect_uri": "http://localhost:51234/callback",
                "email": ANA,
                "created_at": created[2].isoformat(),
                "last_seen_at": None,
            },
        ]

    async def test_revoking_hides_the_client_and_happens_once(self, signed_in, session):
        grant = _grant("client-a")
        session.add(grant)
        await session.commit()
        assert (await signed_in.delete("/api/auth/clients/1")).status_code == 204
        await session.refresh(grant)
        assert grant.revoked_at == NOW
        assert (await signed_in.get("/api/auth/clients")).json() == []
        assert (await signed_in.delete("/api/auth/clients/1")).status_code == 404
        assert (await signed_in.delete("/api/auth/clients/7")).status_code == 404


def _call(subject, name: str, ok: bool, at) -> McpCall:
    return McpCall(kind="tool", name=name, subject=subject, ok=ok, created_at=at)


class TestCallers:
    async def test_no_calls_is_an_empty_list(self, api):
        assert (await api.get("/api/mcp/calls")).json() == []

    async def test_calls_group_by_subject_and_tool_latest_first(self, api, session):
        earlier = NOW - timedelta(hours=2)
        later = NOW - timedelta(hours=1)
        session.add_all(
            [
                _call(BO, "get_metrics", True, earlier - timedelta(hours=1)),
                _call(ANA, "get_metrics", True, earlier),
                _call(ANA, "get_metrics", False, later),
                _call(None, "entity_counts", True, NOW),
            ]
        )
        await session.commit()
        assert (await api.get("/api/mcp/calls")).json() == [
            {
                "subject": None,
                "name": "entity_counts",
                "calls": 1,
                "failed": 0,
                "last_at": NOW.isoformat(),
            },
            {
                "subject": ANA,
                "name": "get_metrics",
                "calls": 2,
                "failed": 1,
                "last_at": later.isoformat(),
            },
            {
                "subject": BO,
                "name": "get_metrics",
                "calls": 1,
                "failed": 0,
                "last_at": (earlier - timedelta(hours=1)).isoformat(),
            },
        ]
