import re
from pathlib import Path

import yaml

from app.caches import DEFINITIONS_DIR

DEFAULT_BRAND_DIR = DEFINITIONS_DIR / "brand"

REQUIRED = (
    "audiences",
    "brand-brain",
    "language",
    "objections",
    "pillars",
    "proof",
    "voice",
)

FRONT_MATTER = re.compile(r"\A---\n(.*?)^---\n", re.DOTALL | re.MULTILINE)


def files(path=None) -> list[str]:
    return sorted(file.stem for file in Path(path or DEFAULT_BRAND_DIR).glob("*.md"))


def read(name, path=None) -> tuple[dict, str]:
    text = (Path(path or DEFAULT_BRAND_DIR) / f"{name}.md").read_text()
    match = FRONT_MATTER.match(text)
    if not match:
        return {}, text
    return yaml.safe_load(match[1]) or {}, text[match.end() :]


def check(path=None) -> list[str]:
    directory = Path(path or DEFAULT_BRAND_DIR)
    if not directory.is_dir():
        return [
            f"brand: {directory.name}/ is not there — every asset is written "
            "against these files, and with none of them a skill has no voice"
        ]
    present = files(directory)
    problems = [
        f"brand: {name}.md is missing — a skill asked for it would write from "
        "whatever the model already believes about this company"
        for name in REQUIRED
        if name not in present
    ]
    problems += [
        f"brand: {name}.md is not one of the brand files — an asset can only "
        f"read {list(REQUIRED)}, so this one is never opened"
        for name in present
        if name not in REQUIRED
    ]
    for name in sorted(set(REQUIRED) & set(present)):
        front, body = read(name, directory)
        if not front:
            problems.append(
                f"brand: {name}.md opens with no front matter — without a title "
                "and a date nothing can say how old the rule it just followed is"
            )
        if not body.strip():
            problems.append(
                f"brand: {name}.md has no body — an empty brand file reads as a "
                "rule that says nothing rather than one nobody wrote"
            )
    return problems
