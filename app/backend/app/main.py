from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import register_routes
from app.db import create_schema


@asynccontextmanager
async def lifespan(app):
    await create_schema()
    yield


app = FastAPI(title="OS v0", lifespan=lifespan)
register_routes(app)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
