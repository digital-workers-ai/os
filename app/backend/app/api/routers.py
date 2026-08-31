from importlib import import_module

from fastapi import APIRouter

sources = APIRouter(prefix="/api", tags=["sources"])
raw = APIRouter(prefix="/api/raw", tags=["raw"])
entities = APIRouter(prefix="/api", tags=["entities"])
metrics = APIRouter(prefix="/api/metrics", tags=["metrics"])

ROUTERS = (sources, raw, entities, metrics)
HANDLER_MODULES = (
    "app.api.raw_api",
    "app.api.sources_api",
    "app.api.entities_api",
    "app.api.metrics_api",
)


def register(app) -> None:
    for module in HANDLER_MODULES:
        import_module(module)
    for router in ROUTERS:
        app.include_router(router)
