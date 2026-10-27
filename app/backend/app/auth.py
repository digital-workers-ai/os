import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import timedelta

import httpx
from fastmcp.server.auth import AccessToken, MultiAuth, TokenVerifier
from fastmcp.server.auth.providers.google import GoogleProvider
from fastmcp.server.auth.redirect_validation import DEFAULT_LOCALHOST_PATTERNS
from fastmcp.server.dependencies import get_access_token
from joserfc.errors import JoseError
from key_value.aio.stores.postgresql import PostgreSQLStore
from key_value.aio.wrappers.encryption import FernetEncryptionWrapper
from mcp.server.auth.provider import TokenError
from sqlalchemy import select

from app import clock, config
from app.config import (
    AUTH_SIGNING_KEY_ENV,
    GOOGLE_CLIENT_ID_ENV,
    GOOGLE_CLIENT_SECRET_ENV,
    settings,
)
from app.db import async_session
from app.models import ApiKey, McpGrant

USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
CLAUDE_CALLBACK = "https://claude.ai/api/mcp/auth_callback"
STORE_TABLE = "oauth_store"
STORE_SALT = "dw-os-oauth-store"
SESSION_COOKIE = "session"
OAUTH_STATE_COOKIE = "oauth_state"
SESSION_TTL_SECONDS = 7 * 24 * 3600
TOUCH_INTERVAL_SECONDS = 60
KEY_PREFIX = "os_"


def allowed(email: str | None) -> bool:
    return email is not None and email.lower() in config.allowed_emails()


def _base64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _signature(encoded: str) -> str:
    key = os.environ[AUTH_SIGNING_KEY_ENV].encode()
    return _base64url(hmac.new(key, encoded.encode(), hashlib.sha256).digest())


def sign_token(payload: dict, ttl_seconds: int) -> str:
    body = {**payload, "exp": int(clock.now().timestamp()) + ttl_seconds}
    encoded = _base64url(json.dumps(body).encode())
    return f"{encoded}.{_signature(encoded)}"


def read_token(value: str | None) -> dict | None:
    if value is None or value.count(".") != 1:
        return None
    encoded, signature = value.split(".")
    if not hmac.compare_digest(signature.encode(), _signature(encoded).encode()):
        return None
    body = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
    if body.pop("exp") <= int(clock.now().timestamp()):
        return None
    return body


def cookie_options() -> dict:
    return {
        "httponly": True,
        "samesite": "lax",
        "secure": settings.PUBLIC_URL.startswith("https://"),
        "path": "/",
    }


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_key() -> str:
    return KEY_PREFIX + secrets.token_urlsafe(32)


def _stale(stamp) -> bool:
    return stamp is None or clock.now() - stamp > timedelta(
        seconds=TOUCH_INTERVAL_SECONDS
    )


async def google_email(access_token: str) -> str | None:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
        )
    if response.status_code != 200:
        return None
    return response.json().get("email")


def store() -> FernetEncryptionWrapper:
    return FernetEncryptionWrapper(
        PostgreSQLStore(
            url=settings.DATABASE_URL.replace("+asyncpg", "", 1),
            table_name=STORE_TABLE,
            auto_create=False,
        ),
        source_material=os.environ[AUTH_SIGNING_KEY_ENV],
        salt=STORE_SALT,
        raise_on_decryption_error=False,
    )


class ApiKeys(TokenVerifier):
    async def verify_token(self, raw):
        if not raw.startswith(KEY_PREFIX):
            return None
        async with async_session() as session:
            row = await session.scalar(
                select(ApiKey).where(
                    ApiKey.key_hash == hash_key(raw), ApiKey.revoked_at.is_(None)
                )
            )
            if row is None or not allowed(row.created_by):
                return None
            if _stale(row.last_used_at):
                row.last_used_at = clock.now()
                await session.commit()
        return AccessToken(
            token=raw,
            client_id=f"key:{row.prefix}",
            scopes=[],
            claims={"email": row.created_by, "key": row.label},
        )


async def _grant(session, client_id: str, email: str) -> McpGrant | None:
    return await session.scalar(
        select(McpGrant).where(McpGrant.client_id == client_id, McpGrant.email == email)
    )


class Google(GoogleProvider):
    def __init__(self):
        super().__init__(
            client_id=os.environ[GOOGLE_CLIENT_ID_ENV],
            client_secret=os.environ[GOOGLE_CLIENT_SECRET_ENV],
            base_url=settings.PUBLIC_URL,
            jwt_signing_key=os.environ[AUTH_SIGNING_KEY_ENV],
            required_scopes=["openid", "email"],
            allowed_client_redirect_uris=[*DEFAULT_LOCALHOST_PATTERNS, CLAUDE_CALLBACK],
            client_storage=store(),
        )

    async def verify_token(self, token):
        verified = await super().verify_token(token)
        if verified is None or not allowed(verified.claims.get("email")):
            return None
        try:
            client_id = self.jwt_issuer.verify_token(token)["client_id"]
        except JoseError:
            return None
        async with async_session() as session:
            grant = await _grant(session, client_id, verified.claims["email"])
            if grant is None:
                return verified
            if grant.revoked_at is not None:
                return None
            if _stale(grant.last_seen_at):
                grant.last_seen_at = clock.now()
                await session.commit()
        return verified

    async def exchange_authorization_code(self, client, authorization_code):
        issued = await super().exchange_authorization_code(client, authorization_code)
        payload = self.jwt_issuer.verify_token(issued.access_token)
        email = payload["upstream_claims"]["email"]
        async with async_session() as session:
            grant = await _grant(session, client.client_id, email)
            if grant is None:
                grant = McpGrant(client_id=client.client_id, email=email)
                session.add(grant)
            grant.client_name = client.client_name
            grant.redirect_uri = (
                str(client.redirect_uris[0]) if client.redirect_uris else None
            )
            grant.last_seen_at = clock.now()
            grant.revoked_at = None
            await session.commit()
        return issued

    async def _extract_upstream_claims(self, idp_tokens):
        email = await google_email(idp_tokens["access_token"])
        if not allowed(email):
            raise TokenError("invalid_grant", f"{email} is not allowed")
        return {"email": email}


def provider() -> MultiAuth | None:
    if not settings.AUTH_ENABLED:
        return None
    config.validate_startup()
    return MultiAuth(server=Google(), verifiers=[ApiKeys()], required_scopes=[])


def subject() -> str | None:
    token = get_access_token()
    if token is None:
        return None
    return token.claims.get("email") or token.client_id
