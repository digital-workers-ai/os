import importlib
import pkgutil

from app import caches
from app.engine import extract as _pkg

HOOK_SOURCES = {
    "hubspot": "firstname + lastname compose into one name",
}


class ExtractError(ValueError):
    pass


_cache: dict | None = None


def _reset() -> None:
    global _cache
    _cache = None


def hooks() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    found = {}
    for info in pkgutil.iter_modules(_pkg.__path__):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"app.engine.extract.{info.name}")
        reshape_fn = getattr(module, "reshape", None)
        if not callable(reshape_fn):
            raise ExtractError(
                f"app/engine/extract/{info.name}.py defines no reshape() — every "
                "module in this package is a source hook"
            )
        source = getattr(module, "SOURCE", info.name)
        if source not in HOOK_SOURCES:
            raise ExtractError(
                f"hook for {source!r} is not listed in HOOK_SOURCES — the "
                "grammar's limits are named, not discovered"
            )
        found[source] = reshape_fn
    _cache = found
    return found


def reshape(source: str, object_type: str, payload: dict) -> list[dict]:
    hook = hooks().get(source)
    if hook is None:
        return [payload]
    records = hook(object_type, payload)
    if isinstance(records, dict):
        records = [records]
    if not isinstance(records, list) or not all(isinstance(r, dict) for r in records):
        raise ExtractError(
            f"{source}.{object_type}: reshape() must return dicts, got "
            f"{type(records).__name__}"
        )
    return records


caches.register(_reset)
