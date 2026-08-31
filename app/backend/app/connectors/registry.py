import importlib
import pkgutil

from app import caches
from app import connectors as _pkg

_INFRA = {"client", "creds", "paginators", "registry", "util"}


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
        name = info.name
        if name.startswith("_") or name in _INFRA:
            continue
        module = importlib.import_module(f"app.connectors.{name}")

        source = getattr(module, "SOURCE", None)
        if not isinstance(source, str) or not source:
            raise ConnectorRegistrationError(
                f"app/connectors/{name}.py defines no SOURCE — every "
                "non-infrastructure module in this package must be a connector"
            )
        pull = getattr(module, "pull", None)
        if not callable(pull):
            raise ConnectorRegistrationError(
                f"connector {source!r} ({name}.py) has no callable pull()"
            )
        if source in found:
            raise ConnectorRegistrationError(
                f"duplicate SOURCE {source!r} ({name}.py and another module)"
            )
        found[source] = module

    _cache = found
    return found


def get(source: str):
    return discover()[source]
