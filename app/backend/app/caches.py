from collections.abc import Callable
from pathlib import Path

import yaml

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"

MAX_OFFSET = 2**63 - 1

_resets: list[Callable[[], None]] = []


def register(reset: Callable[[], None]) -> Callable[[], None]:
    _resets.append(reset)
    return reset


def reset_all() -> None:
    for reset in _resets:
        reset()


def load_mapping(path, error) -> dict:
    path = Path(path)
    doc = yaml.safe_load(path.read_text()) or {}
    if not isinstance(doc, dict):
        raise error(f"{path.name}: top level must be a mapping")
    return doc
