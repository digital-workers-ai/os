from pathlib import Path

import yaml

from app import caches

DEFAULT_LOOKS = caches.DEFINITIONS_DIR / "looks"

FRAMES = {
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
}
MEDIA = ("image", "carousel")
PARTS = ("cover", "slide", "closing")
TEMPLATES = {
    "image": ("card.html.j2",),
    "carousel": ("cover.html.j2", "slide.html.j2", "closing.html.j2"),
}


class LookError(ValueError):
    pass


def names() -> list[str]:
    return sorted(path.name for path in DEFAULT_LOOKS.iterdir() if path.is_dir())


def load(name) -> dict:
    if name not in names():
        raise LookError(f"no look named {name!r} — known: {names()}")
    return caches.load_mapping(DEFAULT_LOOKS / name / "look.yaml", LookError)


def read(name) -> dict:
    folder = DEFAULT_LOOKS / name
    return {
        **load(name),
        "sample": caches.load_mapping(folder / "content.yaml", LookError),
        "layouts": (folder / "layouts.md").read_text(),
    }


def frame(ratio) -> tuple[int, int]:
    if ratio not in FRAMES:
        raise LookError(f"ratio {ratio!r} is not one of {list(FRAMES)}")
    return FRAMES[ratio]


def limits(name, part=None) -> dict:
    manifest = load(name)
    slots = manifest["slots"]
    if manifest["medium"] == "carousel":
        if part not in PARTS:
            raise LookError(f"look {name!r} is a carousel — name a part: {PARTS}")
        slots = slots[part]
    return {slot["name"]: slot["max"] for slot in slots}


def _slot_problems(prefix, slots) -> list[str]:
    if not isinstance(slots, list) or not slots:
        return [f"{prefix} must be a non-empty list of {{name, max}}"]
    problems: list[str] = []
    for slot in slots:
        if not isinstance(slot, dict) or not isinstance(slot.get("name"), str):
            problems.append(
                f"{prefix}: every slot is a mapping with a string `name` and a "
                "whole-number `max`"
            )
            continue
        maximum = slot.get("max")
        if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum < 1:
            problems.append(
                f"{prefix}: slot {slot['name']!r} max {maximum!r} must be a whole "
                "number of at least 1"
            )
    return problems


def _slides_problems(prefix, slides) -> list[str]:
    if not isinstance(slides, dict):
        return [f"{prefix}: slides must be a mapping of min and max"]
    low, high = slides.get("min"), slides.get("max")
    whole = [isinstance(n, int) and not isinstance(n, bool) for n in (low, high)]
    if all(whole) and 1 <= low <= high:
        return []
    return [
        f"{prefix}: slides min {low!r} and max {high!r} must be whole numbers with "
        "1 <= min <= max"
    ]


def _shape_problems(prefix, manifest) -> list[str]:
    slots = manifest.get("slots")
    if manifest["medium"] == "image":
        return _slot_problems(f"{prefix}: slots", slots)
    if not isinstance(slots, dict):
        return [f"{prefix}: slots must be a mapping of {PARTS}"]
    problems: list[str] = []
    for part in PARTS:
        problems += _slot_problems(f"{prefix}: slots.{part}", slots.get(part))
    problems += [
        f"{prefix}: slots.{extra} is not one of {PARTS}"
        for extra in slots
        if extra not in PARTS
    ]
    problems += _slides_problems(prefix, manifest.get("slides"))
    return problems


def _fill_problems(prefix, slots, content) -> list[str]:
    if not isinstance(content, dict):
        return [f"{prefix} must be a mapping of slot → text"]
    problems: list[str] = []
    for slot in slots:
        name, maximum = slot["name"], slot["max"]
        text = content.get(name)
        if not isinstance(text, str) or not text.strip():
            problems.append(f"{prefix} slot {name!r} must be non-empty text")
        elif len(text) > maximum:
            problems.append(
                f"{prefix} slot {name!r} runs {len(text)} chars, past its max of "
                f"{maximum}"
            )
    return problems


def _sample_problems(prefix, manifest, content) -> list[str]:
    slots = manifest["slots"]
    if manifest["medium"] == "image":
        return _fill_problems(prefix, slots, content)
    problems = _fill_problems(f"{prefix} cover", slots["cover"], content.get("cover"))
    low, high = manifest["slides"]["min"], manifest["slides"]["max"]
    slides = content.get("slides")
    if isinstance(slides, list) and low <= len(slides) <= high:
        for number, slide in enumerate(slides, 1):
            problems += _fill_problems(
                f"{prefix} slide {number}", slots["slide"], slide
            )
    else:
        problems.append(
            f"{prefix}: slides must be a list of {low} to {high} slide mappings"
        )
    problems += _fill_problems(
        f"{prefix} closing", slots["closing"], content.get("closing")
    )
    return problems


def _look_problems(folder) -> list[str]:
    name = folder.name
    prefix = f"looks/{name}/look.yaml"
    manifest_path = folder / "look.yaml"
    if not manifest_path.is_file():
        return [f"{prefix} is missing — a look without a manifest has no slots to fill"]
    try:
        manifest = caches.load_mapping(manifest_path, LookError)
    except LookError as e:
        return [f"looks/{name}/{e}"]
    except yaml.YAMLError as e:
        return [f"{prefix} does not parse — {e}"]
    problems: list[str] = []
    if manifest.get("name") != name:
        problems.append(
            f"{prefix}: name {manifest.get('name')!r} is not the directory name "
            f"{name!r}"
        )
    medium = manifest.get("medium")
    if medium not in MEDIA:
        return [*problems, f"{prefix}: medium {medium!r} is not one of {MEDIA}"]
    ratios = manifest.get("ratios")
    if not isinstance(ratios, list) or not ratios:
        problems.append(
            f"{prefix}: ratios must be a non-empty list from {list(FRAMES)}"
        )
    else:
        problems += [
            f"{prefix}: ratio {ratio!r} is not one of {list(FRAMES)}"
            for ratio in ratios
            if not isinstance(ratio, str) or ratio not in FRAMES
        ]
    shape_problems = _shape_problems(prefix, manifest)
    problems += shape_problems
    for template in TEMPLATES[medium]:
        if not (folder / template).is_file():
            problems.append(
                f"looks/{name}/{template} is missing — a {medium} look renders "
                "through it"
            )
    if not (folder / "layouts.md").is_file():
        problems.append(
            f"looks/{name}/layouts.md is missing — a skill reads the frames before "
            "it writes"
        )
    sample_path = folder / "content.yaml"
    if not sample_path.is_file():
        return [
            *problems,
            f"looks/{name}/content.yaml is missing — a look ships a sample that "
            "renders",
        ]
    try:
        content = caches.load_mapping(sample_path, LookError)
    except LookError as e:
        return [*problems, f"looks/{name}/{e}"]
    except yaml.YAMLError as e:
        return [*problems, f"looks/{name}/content.yaml does not parse — {e}"]
    if not shape_problems:
        problems += _sample_problems(f"looks/{name}/content.yaml", manifest, content)
    return problems


def check(path=None) -> list[str]:
    folder = Path(path or DEFAULT_LOOKS)
    if not folder.is_dir():
        return [
            f"looks/: {folder} is not a directory — every image is rendered on a look"
        ]
    problems: list[str] = []
    for look in sorted(entry for entry in folder.iterdir() if entry.is_dir()):
        problems += _look_problems(look)
    return problems
