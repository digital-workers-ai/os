from pathlib import Path

import yaml

from app.caches import DEFINITIONS_DIR

DEFAULT_LOOKS_DIR = DEFINITIONS_DIR / "looks"

MANIFEST = "look.yaml"

SAMPLE = "content.yaml"

IMAGE_TEMPLATE = "card.html.j2"

LAYOUTS = "layouts.md"

PREVIEW = "preview.html"

MEDIA = ("image",)

FRAMES = {
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
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


def sample(name: str, path=None) -> dict:
    return yaml.safe_load((directory(name, path) / SAMPLE).read_text()) or {}


def read(name: str, path=None) -> dict:
    look = directory(name, path)
    layouts = look / LAYOUTS
    return {
        **load(name, path),
        "layouts": layouts.read_text() if layouts.is_file() else "",
        "sample": sample(name, path),
        "dir": str(look),
    }


def frame(name: str, path=None) -> tuple[int, int]:
    return FRAMES[load(name, path)["ratio"]]


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

def _sample_problems(name, path) -> list[str]:
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
        f"look {name!r}: {SAMPLE} fills {extra!r}, which is not a slot this look draws"
        for extra in sorted(set(content) - declared)
    ]
    return problems


def check(path=None) -> list[str]:
    folder = root(path)
    if not folder.is_dir():
        return [
            f"looks: {folder.name}/ is not there — every asset is rendered "
            "through one of these, and with none of them nothing can be built"
        ]
    problems: list[str] = []
    for name in names(path):
        if not (folder / name / MANIFEST).is_file():
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
        if medium in MEDIA and ratio in FRAMES:
            if not (folder / name / IMAGE_TEMPLATE).is_file():
                problems.append(
                    f"look {name!r} has no {IMAGE_TEMPLATE} — an image look "
                    "with no card has nothing to screenshot"
                )
            slot_problems = _slot_problems(name, manifest)
            problems += slot_problems or _sample_problems(name, path)
    return problems
