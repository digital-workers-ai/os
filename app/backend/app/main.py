import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import register_routes
from app.db import create_schema
from app.engine import checks

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    await create_schema()
    problems = checks.run()
    if problems:
        raise checks.BuildCheckError(problems)
    logger.info("build checks: ok")
    yield


app = FastAPI(title="OS v0", lifespan=lifespan)
register_routes(app)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
