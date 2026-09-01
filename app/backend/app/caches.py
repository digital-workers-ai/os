from collections.abc import Callable
from pathlib import Path

import yaml

BACKEND_DIR = Path(__file__).resolve().parent.parent

MAX_OFFSET = 2**63 - 1

_resets: list[Callable[[], None]] = []


def register(reset: Callable[[], None]) -> Callable[[], None]:
    _resets.append(reset)
    return reset


def reset_all() -> None:
    for reset in _resets:
        reset()


def cached(load: Callable[[], dict]) -> Callable[[], dict]:
    box: dict = {}

    def get() -> dict:
        if "value" not in box:
            box["value"] = load()
        return box["value"]

    register(box.clear)
    return get


def load_mapping(path, error) -> dict:
    path = Path(path)
    doc = yaml.safe_load(path.read_text()) or {}
    if not isinstance(doc, dict):
        raise error(f"{path.name}: top level must be a mapping")
    return doc
