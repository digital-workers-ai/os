import logging
from contextlib import asynccontextmanager
from urllib.parse import unquote

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app import mcp
from app.api import register_routes
from app.config import validate_startup
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
    async with mcp.http_app.lifespan(mcp.http_app):
        yield


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


register_routes(app)
app.add_route(mcp.PATH, mcp.http_app)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
