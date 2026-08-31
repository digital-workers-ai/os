import importlib
import pkgutil

from app import caches
from app import sources as _pkg


class ConnectorRegistrationError(RuntimeError):
    pass


_cache: dict | None = None


@caches.register
def _reset() -> None:
    global _cache
    _cache = None


def discover() -> dict:
    global _cache
    if _cache is not None:
        return _cache

    found: dict = {}
    for info in pkgutil.iter_modules(_pkg.__path__):
        if not info.ispkg:
            continue
        name = info.name
        module = importlib.import_module(f"app.sources.{name}.connector")

        source = getattr(module, "SOURCE", None)
        if not isinstance(source, str) or not source:
            raise ConnectorRegistrationError(
                f"app/sources/{name}/connector.py defines no SOURCE — every "
                "source package must name the source its connector serves"
            )
        pull = getattr(module, "pull", None)
        if not callable(pull):
            raise ConnectorRegistrationError(
                f"connector {source!r} ({name}/connector.py) has no callable pull()"
            )
        if source in found:
            raise ConnectorRegistrationError(
                f"duplicate SOURCE {source!r} ({name}/connector.py and another package)"
            )
        found[source] = module

    _cache = found
    return found


def get(source: str):
    return discover()[source]
