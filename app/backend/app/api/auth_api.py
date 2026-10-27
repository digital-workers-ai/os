import hmac
import os
import secrets
from typing import Annotated
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import httpx
from fastapi import Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, StringConstraints
from sqlalchemy import select

from app import auth, clock
from app.api.routers import auth as router
from app.config import GOOGLE_CLIENT_ID_ENV, GOOGLE_CLIENT_SECRET_ENV, settings
from app.db import get_session
from app.models import ApiKey, McpGrant

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
STATE_TTL_SECONDS = 600
PREFIX_LENGTH = 8
BROWSER_ONLY = {403: {"description": "a signed-in browser is required"}}


def _email(request: Request) -> str | None:
    return getattr(request.state, "email", None)


def _browser(request: Request) -> str:
    if not getattr(request.state, "session", False):
        raise HTTPException(403, "manage access from a signed-in browser")
    return request.state.email


def _callback_url() -> str:
    return f"{settings.PUBLIC_URL}/api/auth/callback"


def _safe_next(target: str | None) -> str:
    target = target or "/"
    resolved = urljoin(settings.PUBLIC_URL, target)
    parts = urlsplit(resolved)
    local = parts.scheme in {"http", "https"} and (
        parts.hostname == urlsplit(settings.PUBLIC_URL).hostname
    )
    ambiguous = target.startswith("//") or "\\" in target
    return resolved if local and not ambiguous else "/"


def _with_query(url: str, **params: str) -> str:
    parts = urlsplit(url)
    pairs = [*parse_qsl(parts.query, keep_blank_values=True), *params.items()]
    return urlunsplit(parts._replace(query=urlencode(pairs)))


def _isoformat(value) -> str | None:
    return None if value is None else value.isoformat()


def _return_to(target: str) -> RedirectResponse:
    response = RedirectResponse(target)
    response.delete_cookie(auth.OAUTH_STATE_COOKIE, **auth.cookie_options())
    return response


@router.get("/me")
async def me(request: Request):
    return {
        "auth": "google" if settings.AUTH_ENABLED else "open",
        "email": _email(request),
    }


@router.get("/login", responses={409: {"description": "AUTH_ENABLED is off"}})
async def login(next: str | None = None):
    if not settings.AUTH_ENABLED:
        raise HTTPException(409, "AUTH_ENABLED is off")
    nonce = secrets.token_urlsafe(16)
    query = urlencode(
        {
            "client_id": os.environ[GOOGLE_CLIENT_ID_ENV],
            "redirect_uri": _callback_url(),
            "response_type": "code",
            "scope": "openid email",
            "prompt": "select_account",
            "state": auth.sign_token(
                {"next": _safe_next(next), "nonce": nonce}, STATE_TTL_SECONDS
            ),
        }
    )
    response = RedirectResponse(f"{GOOGLE_AUTH_URL}?{query}")
    response.set_cookie(
        auth.OAUTH_STATE_COOKIE,
        nonce,
        max_age=STATE_TTL_SECONDS,
        **auth.cookie_options(),
    )
    return response


@router.get("/callback", responses={400: {"description": "sign-in did not complete"}})
async def callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    claims = auth.read_token(state)
    if claims is None:
        raise HTTPException(400, "state was not issued by this server")
    held = request.cookies.get(auth.OAUTH_STATE_COOKIE, "")
    if not hmac.compare_digest(claims["nonce"].encode(), held.encode()):
        raise HTTPException(400, "sign-in state does not match this browser")
    target = claims["next"]
    if error is not None or code is None:
        return _return_to(target)
    email = await _google_email(code)
    if not auth.allowed(email):
        return _return_to(_with_query(target, login="denied"))
    response = _return_to(target)
    response.set_cookie(
        auth.SESSION_COOKIE,
        auth.sign_token({"email": email}, auth.SESSION_TTL_SECONDS),
        max_age=auth.SESSION_TTL_SECONDS,
        **auth.cookie_options(),
    )
    return response


async def _google_email(code: str) -> str:
    async with httpx.AsyncClient() as client:
        exchange = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": os.environ[GOOGLE_CLIENT_ID_ENV],
                "client_secret": os.environ[GOOGLE_CLIENT_SECRET_ENV],
                "redirect_uri": _callback_url(),
                "grant_type": "authorization_code",
            },
        )
    if exchange.status_code != 200:
        raise HTTPException(400, "Google refused the code")
    email = await auth.google_email(exchange.json()["access_token"])
    if email is None:
        raise HTTPException(400, "Google refused the token")
    return email


@router.post("/logout", status_code=204)
async def logout():
    response = Response(status_code=204)
    response.delete_cookie(auth.SESSION_COOKIE, **auth.cookie_options())
    return response


class KeyBody(BaseModel):
    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


@router.get("/keys", dependencies=[Depends(_browser)], responses=BROWSER_ONLY)
async def list_keys(session=Depends(get_session)):
    rows = await session.scalars(
        select(ApiKey).where(ApiKey.revoked_at.is_(None)).order_by(ApiKey.seq.desc())
    )
    return [
        {
            "seq": row.seq,
            "prefix": row.prefix,
            "label": row.label,
            "created_by": row.created_by,
            "created_at": row.created_at.isoformat(),
            "last_used_at": _isoformat(row.last_used_at),
        }
        for row in rows
    ]


@router.post("/keys", status_code=201, responses=BROWSER_ONLY)
async def create_key(
    body: KeyBody, email: str = Depends(_browser), session=Depends(get_session)
):
    raw = auth.new_key()
    key = ApiKey(
        key_hash=auth.hash_key(raw),
        prefix=raw[:PREFIX_LENGTH],
        label=body.label,
        created_by=email,
    )
    session.add(key)
    await session.commit()
    return {"seq": key.seq, "prefix": key.prefix, "label": key.label, "key": raw}


@router.delete(
    "/keys/{seq}",
    status_code=204,
    dependencies=[Depends(_browser)],
    responses={**BROWSER_ONLY, 404: {"description": "no live key"}},
)
async def revoke_key(seq: int, session=Depends(get_session)):
    await _revoke(session, ApiKey, seq)


@router.get("/clients", dependencies=[Depends(_browser)], responses=BROWSER_ONLY)
async def list_clients(session=Depends(get_session)):
    rows = await session.scalars(
        select(McpGrant)
        .where(McpGrant.revoked_at.is_(None))
        .order_by(McpGrant.seq.desc())
    )
    return [
        {
            "seq": row.seq,
            "client_name": row.client_name,
            "redirect_uri": row.redirect_uri,
            "email": row.email,
            "created_at": row.created_at.isoformat(),
            "last_seen_at": _isoformat(row.last_seen_at),
        }
        for row in rows
    ]


@router.delete(
    "/clients/{seq}",
    status_code=204,
    dependencies=[Depends(_browser)],
    responses={**BROWSER_ONLY, 404: {"description": "no live client"}},
)
async def revoke_client(seq: int, session=Depends(get_session)):
    await _revoke(session, McpGrant, seq)


async def _revoke(session, model, seq: int) -> None:
    row = await session.scalar(
        select(model).where(model.seq == seq, model.revoked_at.is_(None))
    )
    if row is None:
        raise HTTPException(404, f"no live {model.__tablename__} {seq}")
    row.revoked_at = clock.now()
    await session.commit()
