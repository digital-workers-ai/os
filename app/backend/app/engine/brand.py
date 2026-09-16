import re
from pathlib import Path

import yaml

from app import caches

DEFAULT_BRAND = caches.DEFINITIONS_DIR / "brand"

REQUIRED = (
    "brand-brain.md",
    "voice.md",
    "pillars.md",
    "audiences.md",
    "objections.md",
    "language.md",
    "proof.md",
)
FRONT_KEYS = ("title", "updated")
COLORS = ("ink", "paper", "wash", "line", "muted", "accent")
FONTS = ("sans", "display")
ASSET_TYPES = {".svg": "image/svg+xml", ".woff2": "font/woff2"}

FRONT_MATTER = re.compile(r"\A---\n(.*?)^---\n", re.DOTALL | re.MULTILINE)
COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


class BrandError(ValueError):
    pass


def _split(text) -> tuple[dict, str]:
    match = FRONT_MATTER.match(text)
    if not match:
        return {}, text
    return yaml.safe_load(match[1]) or {}, text[match.end() :]


def files() -> list[str]:
    return list(REQUIRED)


def read(name) -> tuple[dict, str]:
    if name not in REQUIRED:
        raise BrandError(
            f"no brand file named {name!r} — the brand files are {files()}"
        )
    return _split((DEFAULT_BRAND / name).read_text())


def tokens() -> dict:
    return caches.load_mapping(DEFAULT_BRAND / "tokens.yaml", BrandError)


def assets() -> list[dict]:
    folder = DEFAULT_BRAND / "assets"
    return [
        {
            "name": path.name,
            "path": f"assets/{path.name}",
            "media_type": ASSET_TYPES.get(path.suffix, "application/octet-stream"),
            "bytes": path.stat().st_size,
        }
        for path in sorted(folder.iterdir())
        if path.is_file() and not path.name.startswith(".")
    ]


def asset_bytes(name) -> bytes:
    if name not in {asset["name"] for asset in assets()}:
        raise BrandError(f"no brand asset named {name!r}")
    return (DEFAULT_BRAND / "assets" / name).read_bytes()


def _file_problems(folder, name) -> list[str]:
    path = folder / name
    if not path.is_file():
        return [f"brand/{name} is missing — a skill reads all seven brand files"]
    try:
        front, body = _split(path.read_text())
    except yaml.YAMLError as e:
        return [f"brand/{name}: front matter does not parse — {e}"]
    if not isinstance(front, dict):
        return [f"brand/{name}: front matter must be a mapping with title and updated"]
    problems = [
        f"brand/{name}: front matter is missing `{key}`"
        for key in FRONT_KEYS
        if not front.get(key)
    ]
    if not body.strip():
        problems.append(f"brand/{name} has no body under its front matter")
    return problems


def _asset_problems(folder, label, value) -> list[str]:
    if not isinstance(value, str) or Path(value).parent != Path("assets"):
        return [f"brand/tokens.yaml: {label} {value!r} must name a file under assets/"]
    if not (folder / value).is_file():
        return [
            f"brand/tokens.yaml: {label} names {value!r}, which is not a file in "
            "brand/assets/"
        ]
    return []


def _token_problems(folder) -> list[str]:
    path = folder / "tokens.yaml"
    if not path.is_file():
        return ["brand/tokens.yaml is missing — every look reads its colours from it"]
    try:
        doc = caches.load_mapping(path, BrandError)
    except BrandError as e:
        return [f"brand/{e}"]
    except yaml.YAMLError as e:
        return [f"brand/tokens.yaml does not parse — {e}"]
    problems: list[str] = []
    colors = doc.get("colors")
    if isinstance(colors, dict):
        problems += [
            f"brand/tokens.yaml: colors.{name} {colors.get(name)!r} is not a "
            "#RRGGBB colour"
            for name in COLORS
            if not isinstance(colors.get(name), str) or not COLOR.match(colors[name])
        ]
    else:
        problems.append(
            f"brand/tokens.yaml: colors must be a mapping of {', '.join(COLORS)}"
        )
    problems += _asset_problems(folder, "logo", doc.get("logo"))
    fonts = doc.get("fonts")
    if isinstance(fonts, dict):
        for name in FONTS:
            problems += _asset_problems(folder, f"fonts.{name}", fonts.get(name))
    else:
        problems.append(
            "brand/tokens.yaml: fonts must be a mapping of sans and display"
        )
    return problems


def check(path=None) -> list[str]:
    folder = Path(path or DEFAULT_BRAND)
    if not folder.is_dir():
        return [
            f"brand/: {folder} is not a directory — every skill reads the brand "
            "before it writes"
        ]
    problems: list[str] = []
    for name in REQUIRED:
        problems += _file_problems(folder, name)
    problems += [
        f"brand/{extra.name} is not one of the seven brand files — a file nothing "
        "reads is a dead file"
        for extra in sorted(folder.glob("*.md"))
        if extra.name not in REQUIRED
    ]
    problems += _token_problems(folder)
    return problems
