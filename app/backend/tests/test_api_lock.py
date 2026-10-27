from contextlib import asynccontextmanager
from datetime import timedelta
from types import SimpleNamespace

import httpx
import pytest
from fastmcp.server.auth.auth import AccessToken

from app import auth, main, mcp
from app.config import (
    AUTH_SIGNING_KEY_ENV,
    GOOGLE_CLIENT_ID_ENV,
    GOOGLE_CLIENT_SECRET_ENV,
    settings,
)
from tests import conftest
from tests.test_mcp import INITIALIZE, MCP_HEADERS

OPEN = ("/api/health", "/api/auth/login", "/api/auth/callback", "/api/auth/logout")
SIGN_IN = {"detail": "sign in required"}
REFUSED = "refused before reaching the app"
NOBODY = (None, False)


@pytest.fixture
def auth_on(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "AUTH_ALLOWED_EMAILS", "ana@example.com")
    monkeypatch.setattr(settings, "PUBLIC_URL", "http://localhost:8092")
    monkeypatch.setenv(GOOGLE_CLIENT_ID_ENV, "test-client.apps.googleusercontent.com")
    monkeypatch.setenv(GOOGLE_CLIENT_SECRET_ENV, "test-client-secret")
    monkeypatch.setenv(AUTH_SIGNING_KEY_ENV, "test-signing-key")


@asynccontextmanager
async def served():
    seen: list = []

    async def probe(scope, receive, send):
        await main.app(scope, receive, send)
        state = scope.get("state", {})
        seen.append((state["email"], state["session"]) if "email" in state else REFUSED)

    async with main.lifespan(main.app):
        transport = httpx.ASGITransport(app=probe)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://backend"
        ) as api:
            yield api, seen


def _cookie(email="ana@example.com") -> dict:
    return {
        auth.SESSION_COOKIE: auth.sign_token({"email": email}, auth.SESSION_TTL_SECONDS)
    }


def _refused(response) -> None:
    assert response.status_code == 401
    assert response.json() == SIGN_IN
    assert response.headers["www-authenticate"] == "Bearer"


class TestAuthOff:
    async def test_every_api_route_passes_and_nobody_is_named(self):
        async with served() as (api, seen):
            health = await api.get("/api/health")
            described = await api.get("/api/mcp")
        assert (health.status_code, health.json()) == (200, {"status": "ok"})
        assert (described.status_code, described.json()["auth"]) == (200, "open")
        assert seen == [NOBODY, NOBODY]


class TestAuthOn:
    @pytest.fixture(autouse=True)
    def _auth_on(self, auth_on):
        pass

    async def test_a_bare_request_is_told_to_sign_in(self):
        async with served() as (api, seen):
            response = await api.get("/api/mcp")
        _refused(response)
        assert seen == [REFUSED]

    async def test_a_session_cookie_names_the_visitor_as_a_browser(self):
        async with served() as (api, seen):
            response = await api.get("/api/mcp", cookies=_cookie())
        assert (response.status_code, response.json()["auth"]) == (200, "google")
        assert seen == [("ana@example.com", True)]

    async def test_an_expired_cookie_is_told_to_sign_in(self, monkeypatch):
        cookies = _cookie()
        monkeypatch.setattr(
            settings,
            "CLOCK_PINNED_AT",
            conftest.NOW + timedelta(seconds=auth.SESSION_TTL_SECONDS),
        )
        async with served() as (api, seen):
            response = await api.get("/api/mcp", cookies=cookies)
        _refused(response)
        assert seen == [REFUSED]

    async def test_a_cookie_for_an_address_no_longer_allowed_is_told_to_sign_in(
        self,
    ):
        async with served() as (api, seen):
            response = await api.get("/api/mcp", cookies=_cookie("bo@example.com"))
        _refused(response)
        assert seen == [REFUSED]

    async def test_a_bearer_the_provider_accepts_names_the_visitor_not_a_browser(
        self, monkeypatch
    ):
        asked: list[str] = []

        async def verify_token(raw):
            asked.append(raw)
            if raw != "os_good":
                return None
            return AccessToken(
                token=raw,
                client_id="key:os_good",
                scopes=[],
                claims={"email": "ana@example.com", "key": "laptop"},
            )

        monkeypatch.setattr(
            mcp.server, "auth", SimpleNamespace(verify_token=verify_token)
        )
        async with served() as (api, seen):
            accepted = await api.get(
                "/api/mcp", headers={"Authorization": "Bearer os_good"}
            )
            rejected = await api.get(
                "/api/mcp", headers={"Authorization": "Bearer os_bad"}
            )
            basic = await api.get("/api/mcp", headers={"Authorization": "Basic x"})
        assert accepted.status_code == 200
        _refused(rejected)
        _refused(basic)
        assert seen == [("ana@example.com", False), REFUSED, REFUSED]
        assert asked == ["os_good", "os_bad"]

    async def test_health_and_the_sign_in_paths_stay_open(self):
        async with served() as (api, seen):
            responses = [await api.get(path) for path in OPEN]
        assert responses[0].json() == {"status": "ok"}
        assert all(response.status_code != 401 for response in responses)
        assert seen == [NOBODY] * len(OPEN)

    async def test_the_mcp_endpoint_is_not_the_locks_business(self):
        async with served() as (api, seen):
            response = await api.post("/mcp", json=INITIALIZE, headers=MCP_HEADERS)
        assert response.status_code == 200
        assert seen == [NOBODY]
