import hashlib
import json
from datetime import timedelta
from functools import partial

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastmcp import FastMCP
from fastmcp.server.auth import MultiAuth
from fastmcp.server.auth.auth import AccessToken
from fastmcp.server.auth.providers.google import GoogleProvider
from mcp.server.auth.provider import AuthorizationCode, TokenError
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from sqlalchemy import select, text

from app import auth, main
from app.config import (
    AUTH_SIGNING_KEY_ENV,
    GOOGLE_CLIENT_ID_ENV,
    GOOGLE_CLIENT_SECRET_ENV,
    StartupError,
    settings,
)
from app.models import ApiKey, McpGrant
from tests import conftest
from tests.test_mcp import INITIALIZE, MCP_HEADERS

USERINFO = "https://www.googleapis.com/oauth2/v2/userinfo"
AUTH_ROUTES = {
    "/.well-known/oauth-authorization-server",
    "/.well-known/oauth-protected-resource/mcp",
    "/authorize",
    "/token",
    "/register",
    "/auth/callback",
    "/consent",
    "/mcp",
}
CALLBACK = "http://localhost:51234/callback"
CODE = AuthorizationCode(
    code="code-1",
    scopes=[],
    expires_at=0,
    client_id="client-1",
    code_challenge="challenge",
    redirect_uri=CALLBACK,
    redirect_uri_provided_explicitly=True,
)
COOKIE_OPTIONS = {"httponly": True, "samesite": "lax", "path": "/"}


@pytest.fixture
def auth_on(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "AUTH_ALLOWED_EMAILS", "ana@example.com")
    monkeypatch.setattr(settings, "PUBLIC_URL", "http://localhost:8092")
    monkeypatch.setenv(GOOGLE_CLIENT_ID_ENV, "test-client.apps.googleusercontent.com")
    monkeypatch.setenv(GOOGLE_CLIENT_SECRET_ENV, "test-client-secret")
    monkeypatch.setenv(AUTH_SIGNING_KEY_ENV, "test-signing-key")


@pytest_asyncio.fixture
async def minted(session, sessionmaker_for_test, monkeypatch):
    monkeypatch.setattr(auth, "async_session", sessionmaker_for_test)
    monkeypatch.setattr(settings, "AUTH_ALLOWED_EMAILS", "ana@example.com")

    async def _mint(label: str, revoked_at=None) -> tuple[str, ApiKey]:
        raw = auth.new_key()
        row = ApiKey(
            key_hash=auth.hash_key(raw),
            prefix=raw[:8],
            label=label,
            created_by="ana@example.com",
            revoked_at=revoked_at,
        )
        session.add(row)
        await session.commit()
        return raw, row

    return _mint


@pytest_asyncio.fixture
async def google(auth_on, session, sessionmaker_for_test, monkeypatch):
    monkeypatch.setattr(auth, "async_session", sessionmaker_for_test)
    provider = auth.Google()
    provider.set_mcp_path("/mcp")
    return provider


def _token(claims: dict) -> AccessToken:
    return AccessToken(
        token="fastmcp-jwt", client_id="client-1", scopes=["openid"], claims=claims
    )


def _issued(google, client_id="client-1", email="ana@example.com") -> str:
    return google.jwt_issuer.issue_access_token(
        client_id=client_id,
        scopes=["openid"],
        jti="jti-1",
        upstream_claims={"email": email},
    )


def _client(name="Claude Code", redirect=CALLBACK) -> OAuthClientInformationFull:
    return OAuthClientInformationFull(
        client_id="client-1",
        client_name=name,
        redirect_uris=[redirect] if redirect else None,
    )


def _parent_accepts(monkeypatch, email="ana@example.com") -> None:
    async def verified(self, token):
        return _token({"email": email})

    monkeypatch.setattr(GoogleProvider, "verify_token", verified)


def _parent_exchanges(monkeypatch, access_token: str) -> OAuthToken:
    issued = OAuthToken(access_token=access_token, token_type="Bearer")

    async def exchanged(self, client, authorization_code):
        return issued

    monkeypatch.setattr(GoogleProvider, "exchange_authorization_code", exchanged)
    return issued


async def _granted(session, revoked_at=None, seen=conftest.FIXTURE_SEEN) -> McpGrant:
    grant = McpGrant(
        client_id="client-1",
        email="ana@example.com",
        last_seen_at=seen,
        revoked_at=revoked_at,
    )
    session.add(grant)
    await session.commit()
    return grant


async def _grants(session) -> list[McpGrant]:
    return list(await session.scalars(select(McpGrant).order_by(McpGrant.seq)))


def _bare_app() -> FastAPI:
    return FastAPI(openapi_url=None, docs_url=None, redoc_url=None)


def _userinfo(monkeypatch, body: dict, status: int = 200) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def handler(request):
        seen.append(request)
        return httpx.Response(status, json=body)

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        partial(httpx.AsyncClient, transport=httpx.MockTransport(handler)),
    )
    return seen


class TestAllowed:
    def test_only_a_listed_address_is_allowed_whatever_its_case(self, monkeypatch):
        monkeypatch.setattr(settings, "AUTH_ALLOWED_EMAILS", "Ana@Example.com")
        assert auth.allowed("ana@example.com")
        assert auth.allowed("ANA@example.com")
        assert not auth.allowed("bo@example.com")
        assert not auth.allowed(None)


class TestSignedTokens:
    @pytest.fixture(autouse=True)
    def _signing_key(self, monkeypatch):
        monkeypatch.setenv(AUTH_SIGNING_KEY_ENV, "test-signing-key")

    def test_a_signed_payload_reads_back_without_its_expiry(self):
        token = auth.sign_token({"email": "ana@example.com"}, 60)
        assert token.count(".") == 1
        assert "=" not in token
        assert auth.read_token(token) == {"email": "ana@example.com"}

    def test_a_token_expires_at_its_ttl_and_not_before(self, monkeypatch):
        token = auth.sign_token({"email": "ana@example.com"}, 60)
        monkeypatch.setattr(
            settings, "CLOCK_PINNED_AT", conftest.NOW + timedelta(seconds=59)
        )
        assert auth.read_token(token) == {"email": "ana@example.com"}
        monkeypatch.setattr(
            settings, "CLOCK_PINNED_AT", conftest.NOW + timedelta(seconds=60)
        )
        assert auth.read_token(token) is None

    def test_a_payload_swapped_under_a_signature_is_refused(self):
        ana, bo = (
            auth.sign_token({"email": email}, 60)
            for email in ("ana@example.com", "bo@example.com")
        )
        payload, _ = bo.split(".")
        _, signature = ana.split(".")
        assert auth.read_token(f"{payload}.{signature}") is None
        assert auth.read_token(f"{payload}.{signature[:-1]}") is None

    def test_a_token_signed_under_another_key_is_refused(self, monkeypatch):
        token = auth.sign_token({"email": "ana@example.com"}, 60)
        monkeypatch.setenv(AUTH_SIGNING_KEY_ENV, "another-key")
        assert auth.read_token(token) is None

    @pytest.mark.parametrize(
        "value", [None, "", "nonsense", "a.b.c", ".", "payload.", ".sig", "pay.ñ"]
    )
    def test_anything_else_reads_as_nothing(self, value):
        assert auth.read_token(value) is None

    def test_the_session_cookie_lives_a_week(self):
        assert auth.SESSION_COOKIE == "session"
        assert auth.SESSION_TTL_SECONDS == 7 * 24 * 3600

    def test_the_sign_in_state_travels_in_its_own_cookie(self):
        assert auth.OAUTH_STATE_COOKIE == "oauth_state"


class TestCookieOptions:
    def test_over_https_the_cookie_is_secure(self, monkeypatch):
        monkeypatch.setattr(settings, "PUBLIC_URL", "https://os.example.com")
        assert auth.cookie_options() == {**COOKIE_OPTIONS, "secure": True}

    def test_on_loopback_http_it_is_not(self, monkeypatch):
        monkeypatch.setattr(settings, "PUBLIC_URL", "http://localhost:8092")
        assert auth.cookie_options() == {**COOKIE_OPTIONS, "secure": False}


class TestKeys:
    def test_a_new_key_is_prefixed_long_and_never_repeats(self):
        first, second = auth.new_key(), auth.new_key()
        assert first.startswith("os_") and second.startswith("os_")
        assert len(first) == len("os_") + 43
        assert first != second

    def test_hashing_is_sha256_hex(self):
        assert auth.hash_key("os_abc") == hashlib.sha256(b"os_abc").hexdigest()
        assert len(auth.hash_key(auth.new_key())) == 64


class TestApiKeys:
    async def test_a_live_key_names_its_maker_and_records_the_use(
        self, minted, session, monkeypatch
    ):
        raw, row = await minted("laptop")
        later = conftest.NOW + timedelta(minutes=5)
        monkeypatch.setattr(settings, "CLOCK_PINNED_AT", later)
        token = await auth.ApiKeys().verify_token(raw)
        assert (token.token, token.client_id, token.scopes) == (
            raw,
            f"key:{raw[:8]}",
            [],
        )
        assert token.claims == {"email": "ana@example.com", "key": "laptop"}
        await session.refresh(row)
        assert row.last_used_at == later

    async def test_a_use_within_the_minute_is_not_recorded_again(
        self, minted, session, monkeypatch
    ):
        assert auth.TOUCH_INTERVAL_SECONDS == 60
        raw, row = await minted("laptop")
        await auth.ApiKeys().verify_token(raw)
        for seconds, recorded in ((30, 0), (60, 0), (61, 61)):
            monkeypatch.setattr(
                settings, "CLOCK_PINNED_AT", conftest.NOW + timedelta(seconds=seconds)
            )
            token = await auth.ApiKeys().verify_token(raw)
            assert token.claims["key"] == "laptop"
            await session.refresh(row)
            assert row.last_used_at == conftest.NOW + timedelta(seconds=recorded)

    async def test_a_revoked_key_is_refused_and_leaves_no_trace(self, minted, session):
        raw, row = await minted("laptop", revoked_at=conftest.NOW)
        assert await auth.ApiKeys().verify_token(raw) is None
        await session.refresh(row)
        assert row.last_used_at is None

    async def test_a_key_whose_maker_is_no_longer_allowed_is_refused(
        self, minted, session, monkeypatch
    ):
        raw, row = await minted("laptop")
        monkeypatch.setattr(settings, "AUTH_ALLOWED_EMAILS", "bo@example.com")
        assert await auth.ApiKeys().verify_token(raw) is None
        await session.refresh(row)
        assert row.last_used_at is None

    async def test_an_unknown_key_is_refused(self, minted):
        await minted("laptop")
        assert await auth.ApiKeys().verify_token(auth.new_key()) is None

    async def test_anything_but_a_key_never_reaches_the_table(
        self, minted, count_queries
    ):
        with count_queries() as counter:
            assert await auth.ApiKeys().verify_token("fastmcp-jwt") is None
        assert counter.total == 0


class TestProvider:
    def test_auth_off_serves_the_endpoint_open(self):
        assert auth.provider() is None

    def test_auth_on_composes_google_with_keys_and_keeps_every_oauth_route(
        self, auth_on
    ):
        provider = auth.provider()
        assert isinstance(provider, MultiAuth)
        assert isinstance(provider.server, auth.Google)
        assert isinstance(provider.server, GoogleProvider)
        [verifier] = provider.verifiers
        assert isinstance(verifier, auth.ApiKeys)
        http_app = FastMCP("t", auth=provider).http_app(path="/mcp")
        assert {route.path for route in http_app.routes} == AUTH_ROUTES

    def test_auth_on_without_a_credential_is_told_what_to_set(
        self, auth_on, monkeypatch
    ):
        monkeypatch.delenv(AUTH_SIGNING_KEY_ENV)
        with pytest.raises(StartupError, match=AUTH_SIGNING_KEY_ENV) as info:
            auth.provider()
        assert "Set a credential, or switch it off" in str(info.value)

    async def test_a_key_opens_the_endpoint_that_refuses_a_bare_call(
        self, auth_on, minted, session
    ):
        raw, row = await minted("laptop")
        http_app = FastMCP("t", auth=auth.provider()).http_app(path="/mcp")
        async with http_app.lifespan(http_app):
            transport = httpx.ASGITransport(app=http_app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://backend"
            ) as api:
                bare = await api.post("/mcp", json=INITIALIZE, headers=MCP_HEADERS)
                keyed = await api.post(
                    "/mcp",
                    json=INITIALIZE,
                    headers={**MCP_HEADERS, "Authorization": f"Bearer {raw}"},
                )
        assert bare.status_code == 401
        assert keyed.status_code == 200
        await session.refresh(row)
        assert row.last_used_at == conftest.NOW


class TestVerifyToken:
    @pytest.fixture(autouse=True)
    def _auth_on(self, auth_on):
        pass

    async def test_a_token_for_a_listed_address_passes(self, google, monkeypatch):
        issued = _issued(google)

        async def verified(self, token):
            assert token == issued
            return _token({"email": "ana@example.com"})

        monkeypatch.setattr(GoogleProvider, "verify_token", verified)
        token = await google.verify_token(issued)
        assert token.claims["email"] == "ana@example.com"

    async def test_a_token_for_a_stranger_is_refused(self, monkeypatch):
        _parent_accepts(monkeypatch, "bo@example.com")
        assert await auth.Google().verify_token("fastmcp-jwt") is None

    async def test_a_token_google_refuses_stays_refused(self, monkeypatch):
        async def verified(self, token):
            return None

        monkeypatch.setattr(GoogleProvider, "verify_token", verified)
        assert await auth.Google().verify_token("fastmcp-jwt") is None

    async def test_a_live_grant_lets_the_token_through_and_marks_the_visit(
        self, google, session, monkeypatch
    ):
        grant = await _granted(session)
        _parent_accepts(monkeypatch)
        token = await google.verify_token(_issued(google))
        assert token.claims["email"] == "ana@example.com"
        await session.refresh(grant)
        assert grant.last_seen_at == conftest.NOW

    async def test_a_visit_within_the_minute_is_not_marked_again(
        self, google, session, monkeypatch
    ):
        recent = conftest.NOW - timedelta(seconds=30)
        grant = await _granted(session, seen=recent)
        _parent_accepts(monkeypatch)
        token = await google.verify_token(_issued(google))
        assert token.claims["email"] == "ana@example.com"
        await session.refresh(grant)
        assert grant.last_seen_at == recent

    async def test_a_revoked_grant_refuses_the_token(
        self, google, session, monkeypatch
    ):
        grant = await _granted(session, revoked_at=conftest.NOW)
        _parent_accepts(monkeypatch)
        assert await google.verify_token(_issued(google)) is None
        await session.refresh(grant)
        assert grant.last_seen_at == conftest.FIXTURE_SEEN

    async def test_a_token_from_before_grants_were_kept_still_passes(
        self, google, session, monkeypatch
    ):
        _parent_accepts(monkeypatch)
        token = await google.verify_token(_issued(google))
        assert token.claims["email"] == "ana@example.com"
        assert await _grants(session) == []

    async def test_a_token_the_issuer_rejects_is_refused_whatever_google_says(
        self, google, monkeypatch
    ):
        _parent_accepts(monkeypatch)
        assert await google.verify_token("fastmcp-jwt") is None


class TestGrants:
    async def test_exchanging_a_code_records_who_granted_which_client(
        self, google, session, monkeypatch
    ):
        issued = _parent_exchanges(monkeypatch, _issued(google))
        assert await google.exchange_authorization_code(_client(), CODE) is issued
        [grant] = await _grants(session)
        assert (grant.client_id, grant.client_name, grant.redirect_uri) == (
            "client-1",
            "Claude Code",
            CALLBACK,
        )
        assert grant.email == "ana@example.com"
        assert grant.last_seen_at == conftest.NOW
        assert grant.created_at is not None
        assert grant.revoked_at is None

    async def test_a_client_without_a_redirect_is_recorded_without_one(
        self, google, session, monkeypatch
    ):
        _parent_exchanges(monkeypatch, _issued(google))
        await google.exchange_authorization_code(_client(redirect=None), CODE)
        [grant] = await _grants(session)
        assert grant.redirect_uri is None

    async def test_re_authorizing_refreshes_the_grant_and_lifts_a_revocation(
        self, google, session, monkeypatch
    ):
        _parent_exchanges(monkeypatch, _issued(google))
        await google.exchange_authorization_code(_client(), CODE)
        [grant] = await _grants(session)
        grant.revoked_at = conftest.NOW
        await session.commit()
        later = conftest.NOW + timedelta(days=1)
        monkeypatch.setattr(settings, "CLOCK_PINNED_AT", later)
        again = _client(name="Claude Desktop", redirect="http://localhost:9/cb")
        await google.exchange_authorization_code(again, CODE)
        assert len(await _grants(session)) == 1
        await session.refresh(grant)
        assert (grant.client_name, grant.redirect_uri) == (
            "Claude Desktop",
            "http://localhost:9/cb",
        )
        assert (grant.last_seen_at, grant.revoked_at) == (later, None)


class TestUpstreamClaims:
    @pytest.fixture(autouse=True)
    def _auth_on(self, auth_on):
        pass

    async def test_the_address_google_reports_becomes_the_claim(self, monkeypatch):
        seen = _userinfo(monkeypatch, {"email": "ana@example.com", "name": "Ana"})
        claims = await auth.Google()._extract_upstream_claims(
            {"access_token": "google-access-token", "id_token": "google-id-token"}
        )
        assert claims == {"email": "ana@example.com"}
        [request] = seen
        assert str(request.url) == USERINFO
        assert request.headers["Authorization"] == "Bearer google-access-token"

    async def test_a_stranger_is_an_oauth_error_not_a_token(self, monkeypatch):
        _userinfo(monkeypatch, {"email": "bo@example.com"})
        with pytest.raises(TokenError) as info:
            await auth.Google()._extract_upstream_claims(
                {"access_token": "google-access-token"}
            )
        assert info.value.error == "invalid_grant"
        assert info.value.error_description == "bo@example.com is not allowed"

    async def test_no_address_from_google_is_an_oauth_error_too(self, monkeypatch):
        _userinfo(monkeypatch, {"error": "invalid_token"}, status=401)
        with pytest.raises(TokenError) as info:
            await auth.Google()._extract_upstream_claims(
                {"access_token": "google-access-token"}
            )
        assert info.value.error == "invalid_grant"


class TestGoogleEmail:
    async def test_the_address_comes_back_from_userinfo(self, monkeypatch):
        seen = _userinfo(monkeypatch, {"email": "ana@example.com", "name": "Ana"})
        assert await auth.google_email("google-access-token") == "ana@example.com"
        [request] = seen
        assert str(request.url) == USERINFO
        assert request.headers["Authorization"] == "Bearer google-access-token"

    @pytest.mark.parametrize(
        ("status", "body"),
        [(401, {"error": "invalid_token"}), (200, {"name": "Ana"})],
    )
    async def test_a_refusal_or_a_missing_address_is_nothing(
        self, monkeypatch, status, body
    ):
        _userinfo(monkeypatch, body, status=status)
        assert await auth.google_email("google-access-token") is None


class TestStore:
    async def test_values_travel_encrypted_through_oauth_store(
        self, auth_on, monkeypatch, session, db_engine
    ):
        monkeypatch.setattr(settings, "DATABASE_URL", conftest.test_database_url())
        store = auth.store()
        assert store.key_value._table_name == "oauth_store"
        async with store.key_value:
            await store.put("code-1", {"secret": "plain"}, collection="codes")
            assert await store.get("code-1", collection="codes") == {"secret": "plain"}
        async with db_engine.connect() as conn:
            rows = await conn.execute(
                text("select collection, key, value from oauth_store")
            )
            [(collection, key, value)] = rows.all()
        assert (collection, key) == ("codes", "code-1")
        assert "plain" not in json.dumps(value)


class TestSubject:
    def test_outside_a_request_there_is_no_subject(self):
        assert auth.subject() is None

    def test_no_token_means_no_subject(self, monkeypatch):
        monkeypatch.setattr(auth, "get_access_token", lambda: None)
        assert auth.subject() is None

    def test_the_email_claim_names_the_subject(self, monkeypatch):
        monkeypatch.setattr(
            auth, "get_access_token", lambda: _token({"email": "ana@example.com"})
        )
        assert auth.subject() == "ana@example.com"

    async def test_a_key_token_names_its_maker(self, minted, monkeypatch):
        raw, _ = await minted("laptop")
        token = await auth.ApiKeys().verify_token(raw)
        monkeypatch.setattr(auth, "get_access_token", lambda: token)
        assert auth.subject() == "ana@example.com"

    def test_without_an_email_the_client_id_stands_in(self, monkeypatch):
        monkeypatch.setattr(auth, "get_access_token", lambda: _token({}))
        assert auth.subject() == "client-1"


class TestMount:
    async def test_every_route_of_an_authenticated_server_is_served(self, auth_on):
        app = _bare_app()
        http_app = FastMCP("t", auth=auth.provider()).http_app(path="/mcp")
        main.mount(app, http_app)
        assert {route.path for route in app.routes} == AUTH_ROUTES
        assert all(route.endpoint is http_app for route in app.routes)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://backend"
        ) as api:
            metadata = (await api.get("/.well-known/oauth-authorization-server")).json()
        assert metadata["issuer"] == "http://localhost:8092/"
        assert metadata["authorization_endpoint"] == "http://localhost:8092/authorize"
        assert metadata["token_endpoint"] == "http://localhost:8092/token"

    def test_an_open_server_is_only_the_endpoint(self):
        app = _bare_app()
        http_app = FastMCP("t").http_app(path="/mcp")
        main.mount(app, http_app)
        assert [route.path for route in app.routes] == ["/mcp"]
