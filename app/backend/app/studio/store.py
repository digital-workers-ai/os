import json
from pathlib import Path

from app.config import settings

DIRECTORY = "studio"


def path(name):
    return Path(settings.MEDIA_DIR) / DIRECTORY / name


def read_text(name):
    try:
        return path(name).read_text()
    except OSError:
        return None


def write_text(name, text):
    target = path(name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


def read_json(name):
    text = read_text(name)
    try:
        found = json.loads(text)
    except (TypeError, ValueError):
        return {}
    return found if isinstance(found, dict) else {}


def write_json(name, value):
    write_text(name, json.dumps(value))
