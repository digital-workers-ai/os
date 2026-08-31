from importlib import import_module

from fastapi import APIRouter

sources = APIRouter(prefix="/api", tags=["sources"])
raw = APIRouter(prefix="/api/raw", tags=["raw"])

ROUTERS = (sources, raw)
HANDLER_MODULES = ("app.api.raw_api", "app.api.sources_api")


def register(app) -> None:
    for module in HANDLER_MODULES:
        import_module(module)
    for router in ROUTERS:
        app.include_router(router)
