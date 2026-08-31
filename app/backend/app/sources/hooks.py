import importlib
import importlib.util
import pkgutil

from app import caches
from app import sources as _pkg


class ExtractError(ValueError):
    pass


_cache: dict | None = None


@caches.register
def _reset() -> None:
    global _cache
    _cache = None


def with_name(
    payload: dict, first_field: str, last_field: str, source_record: dict | None = None
) -> dict:
    fields = source_record if source_record is not None else payload
    parts = [str(fields.get(key) or "").strip() for key in (first_field, last_field)]
    name = " ".join(part for part in parts if part)
    record = dict(payload)
    if name:
        record["_full_name"] = name
    return record


def hooks() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    found = {}
    for info in pkgutil.iter_modules(_pkg.__path__):
        if not info.ispkg:
            continue
        module_name = f"app.sources.{info.name}.extract"
        if importlib.util.find_spec(module_name) is None:
            continue
        module = importlib.import_module(module_name)
        reshape_fn = getattr(module, "reshape", None)
        if not callable(reshape_fn):
            raise ExtractError(
                f"app/sources/{info.name}/extract.py defines no reshape() — a "
                "source's extract module is its hook"
            )
        found[info.name] = reshape_fn
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
