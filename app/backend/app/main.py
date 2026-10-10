import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from urllib.parse import unquote

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app import auth, mcp
from app.agents import marketer
from app.api import register_routes
from app.config import settings, validate_startup
from app.db import create_schema
from app.engine import checks

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    validate_startup()
    await create_schema()
    problems = checks.run()
    if problems:
        raise checks.BuildCheckError(problems)
    logger.info("build checks: ok")
    daily = asyncio.create_task(marketer.daily()) if settings.MARKETER_DAILY else None
    async with mcp.http_app.lifespan(mcp.http_app):
        yield
    if daily is not None:
        daily.cancel()
        with suppress(asyncio.CancelledError):
            await daily


app = FastAPI(title="OS", lifespan=lifespan)


@app.middleware("http")
async def refuse_null_bytes(request, call_next):
    message = "value contains a null byte, which cannot be stored or compared as text"
    for name, value in request.query_params.multi_items():
        if "\x00" in value:
            return JSONResponse(
                status_code=422,
                content={
                    "detail": [
                        {
                            "loc": ["query", name],
                            "msg": message,
                            "type": "value_error.null_byte",
                        }
                    ]
                },
            )
    if "\x00" in unquote(request.url.path):
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {
                        "loc": ["path"],
                        "msg": message,
                        "type": "value_error.null_byte",
                    }
                ]
            },
        )
    return await call_next(request)


OPEN_PATHS = frozenset(
    {"/api/health", "/api/auth/login", "/api/auth/callback", "/api/auth/logout"}
)


async def _admit(request, call_next, email=None, session=False):
    request.state.email = email
    request.state.session = session
    return await call_next(request)


@app.middleware("http")
async def lock_api(request, call_next):
    path = request.url.path
    if not path.startswith("/api/") or path in OPEN_PATHS or not settings.AUTH_ENABLED:
        return await _admit(request, call_next)
    cookie = auth.read_token(request.cookies.get(auth.SESSION_COOKIE)) or {}
    if auth.allowed(cookie.get("email")):
        return await _admit(request, call_next, cookie["email"], session=True)
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        token = await mcp.server.auth.verify_token(header.removeprefix("Bearer "))
        if token is not None:
            return await _admit(request, call_next, token.claims.get("email"))
    return JSONResponse(
        status_code=401,
        content={"detail": "sign in required"},
        headers={"WWW-Authenticate": "Bearer"},
    )


def mount(app: FastAPI, http_app) -> None:
    for route in http_app.routes:
        app.add_route(route.path, http_app)


register_routes(app)
mount(app, mcp.http_app)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
