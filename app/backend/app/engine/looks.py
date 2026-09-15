import importlib.util
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.caches import DEFINITIONS_DIR

DEFAULT_LOOKS_DIR = DEFINITIONS_DIR / "looks"

MANIFEST = "look.yaml"

SAMPLE = "content.yaml"

SCHEMA = "template.py"

VIDEO_TEMPLATE = "base.html.j2"

IMAGE_TEMPLATE = "card.html.j2"

LAYOUTS = "layouts.md"

PREVIEW = "preview.html"

FRAMES_DIR = "images"

SHARED = "_shared"

MEDIA = ("video", "image")

SYMBOLS = ("ContentSpec", "PLANNER_PROMPT")

FRAMES = {
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
}

RESOLUTIONS = {
    "1:1": "square",
    "4:5": "four-five",
    "9:16": "portrait",
    "16:9": "landscape",
}


class LookError(ValueError):
    pass


def root(path=None) -> Path:
    return Path(path or DEFAULT_LOOKS_DIR)


def names(path=None) -> list[str]:
    directory = root(path)
    if not directory.is_dir():
        return []
    return sorted(
        child.name
        for child in directory.iterdir()
        if child.is_dir() and not child.name.startswith("_")
    )


def directory(name: str, path=None) -> Path:
    found = root(path) / name
    if not (found / MANIFEST).is_file():
        raise LookError(
            f"no look {name!r} in {root(path)} — have: "
            f"{', '.join(names(path)) or 'none'}"
        )
    return found


def load(name: str, path=None) -> dict:
    doc = yaml.safe_load((directory(name, path) / MANIFEST).read_text()) or {}
    if not isinstance(doc, dict):
        raise LookError(f"{name}/{MANIFEST}: top level must be a mapping")
    return doc


def module(name: str, path=None):
    entry = directory(name, path) / SCHEMA
    if not entry.is_file():
        raise LookError(
            f"look {name!r} has no {SCHEMA}, so it declares no scene vocabulary"
        )
    spec = importlib.util.spec_from_file_location(f"looks.{name}", entry)
    imported = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(imported)
    missing = [symbol for symbol in SYMBOLS if not hasattr(imported, symbol)]
    if missing:
        raise LookError(f"look {name!r} {SCHEMA} defines no {', '.join(missing)}")
    return imported


def schema(name: str, path=None):
    return module(name, path).ContentSpec


def prompt(name: str, path=None) -> str:
    return module(name, path).PLANNER_PROMPT


def sample(name: str, path=None) -> dict:
    return yaml.safe_load((directory(name, path) / SAMPLE).read_text()) or {}


def frames(name: str, path=None) -> list[str]:
    stills = directory(name, path) / FRAMES_DIR
    if not stills.is_dir():
        return []
    return sorted(
        f"{FRAMES_DIR}/{still.name}" for still in stills.iterdir() if still.is_file()
    )


def read(name: str, path=None) -> dict:
    look = directory(name, path)
    layouts = look / LAYOUTS
    return {
        **load(name, path),
        "layouts": layouts.read_text() if layouts.is_file() else "",
        "sample": sample(name, path),
        "frames": frames(name, path),
        "dir": str(look),
    }


def frame(name: str, path=None) -> tuple[int, int]:
    return FRAMES[load(name, path)["ratio"]]


def resolution(name: str, path=None) -> str:
    return RESOLUTIONS[load(name, path)["ratio"]]


def limits(name: str, path=None) -> dict[str, int]:
    return {
        str(slot["name"]): int(slot["max"])
        for slot in load(name, path).get("slots") or []
    }


def _slot_problems(name, manifest) -> list[str]:
    slots = manifest.get("slots")
    if not isinstance(slots, list) or not slots:
        return [
            f"look {name!r}: an image look must list the `slots:` its card "
            "holds — without them nothing knows how long a line may be"
        ]
    return [
        f"look {name!r}: slot {slot.get('name')!r} declares no `max:` — a "
        "limit nobody wrote down is a limit nobody enforces"
        for slot in slots
        if not isinstance(slot, dict) or not slot.get("name") or not slot.get("max")
    ]


def _image_sample_problems(name, manifest, path) -> list[str]:
    try:
        content = sample(name, path)
    except FileNotFoundError:
        return [
            f"look {name!r} ships no {SAMPLE} — a look with no sample has "
            "never been rendered end to end"
        ]
    problems = []
    for slot, ceiling in limits(name, path).items():
        written = content.get(slot)
        if not isinstance(written, str):
            problems.append(f"look {name!r}: {SAMPLE} fills no {slot!r} slot")
            continue
        if len(written) > ceiling:
            problems.append(
                f"look {name!r}: {SAMPLE} writes {len(written)} characters into "
                f"{slot!r}, which holds {ceiling}"
            )
    declared = set(limits(name, path))
    problems += [
        f"look {name!r}: {SAMPLE} fills {extra!r}, which is not a slot this "
        "look draws"
        for extra in sorted(set(content) - declared)
    ]
    return problems


def _video_problems(name, manifest, path) -> list[str]:
    problems: list[str] = []
    look = root(path) / name
    if not (look / VIDEO_TEMPLATE).is_file():
        problems.append(
            f"look {name!r} has no {VIDEO_TEMPLATE} — a video look with no "
            "markup composes to an empty page"
        )
    if manifest.get("voice_confirmed") and not manifest.get("voice"):
        problems.append(
            f"look {name!r} says its voice is confirmed and names none — "
            "a confirmation of nothing is how an unheard voice ships"
        )
    try:
        spec = schema(name, path)
    except LookError as error:
        return problems + [str(error)]
    except Exception as error:
        return problems + [f"look {name!r} {SCHEMA} will not import: {error}"]
    try:
        spec(**sample(name, path))
    except FileNotFoundError:
        problems.append(
            f"look {name!r} ships no {SAMPLE} — a look with no sample has "
            "never been rendered end to end"
        )
    except ValidationError as error:
        problems.append(
            f"look {name!r}: {SAMPLE} does not validate against its own "
            f"schema: {error}"
        )
    else:
        shape = resolution(name, path)
        written = sample(name, path).get("project", {}).get("resolution")
        if written and written != shape:
            problems.append(
                f"look {name!r}: {SAMPLE} lays out for {written!r} and the "
                f"manifest says {manifest['ratio']!r}, which is {shape!r} — "
                "the composed frame would not be the shape the look declares"
            )
    return problems


def check(path=None) -> list[str]:
    directory = root(path)
    if not directory.is_dir():
        return [
            f"looks: {directory.name}/ is not there — every asset is rendered "
            "through one of these, and with none of them nothing can be built"
        ]
    problems: list[str] = []
    for name in sorted(
        child.name
        for child in directory.iterdir()
        if child.is_dir() and child.name != SHARED
    ):
        if not (directory / name / MANIFEST).is_file():
            problems.append(
                f"look {name!r} has no {MANIFEST} — the manifest is how a look "
                "describes itself without anything importing its Python"
            )
            continue
        try:
            manifest = load(name, path)
        except (LookError, yaml.YAMLError) as error:
            problems.append(f"look {name!r}: {error}")
            continue
        medium = manifest.get("medium")
        if medium not in MEDIA:
            problems.append(
                f"look {name!r}: medium {medium!r} is not something this "
                f"renders — known: {list(MEDIA)}"
            )
        ratio = manifest.get("ratio")
        if ratio not in FRAMES:
            problems.append(
                f"look {name!r}: ratio {ratio!r} is not a shape any feed "
                f"shows — known: {list(FRAMES)}"
            )
        if medium == "video" and ratio in FRAMES:
            problems += _video_problems(name, manifest, path)
        if medium == "image" and ratio in FRAMES:
            if not (directory / name / IMAGE_TEMPLATE).is_file():
                problems.append(
                    f"look {name!r} has no {IMAGE_TEMPLATE} — an image look "
                    "with no card has nothing to screenshot"
                )
            slot_problems = _slot_problems(name, manifest)
            problems += slot_problems or _image_sample_problems(name, manifest, path)
    return problems
