import hashlib
import re
from dataclasses import dataclass

import yaml

from app.caches import BACKEND_DIR

SKILLS_DIR = BACKEND_DIR / ".claude" / "skills"
PREFIX = "dw-"
KINDS = ("post", "newsletter", "blog", "image", "carousel")
LESSONS_HEADING = "## Lessons"

_FRONT_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)


class SkillError(ValueError):
    pass


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    makes: str
    body: str
    lessons: tuple[str, ...]
    sha: str


def _refuse(name, reason):
    raise SkillError(f"skill {name!r}: {reason}")


def _split(name, text) -> tuple[dict, str]:
    match = _FRONT_RE.match(text)
    front = yaml.safe_load(match.group(1)) if match else None
    if not isinstance(front, dict):
        _refuse(name, "SKILL.md has no front matter")
    return front, match.group(2).lstrip("\n")


def _makes(name, front) -> str:
    makes = front.get("makes")
    if makes is None:
        _refuse(name, "front matter has no makes")
    if makes not in KINDS:
        _refuse(name, f"makes {makes!r} is not one of {', '.join(KINDS)}")
    return makes


def _lessons(name, body) -> tuple[str, ...]:
    lines = body.splitlines()
    if LESSONS_HEADING not in lines:
        _refuse(name, f"has no `{LESSONS_HEADING}` heading")
    lessons: list[str] = []
    for line in lines[lines.index(LESSONS_HEADING) + 1 :]:
        if line.startswith("## "):
            break
        if line.startswith("- "):
            lessons.append(line[2:].strip())
        elif line.startswith("  ") and lessons:
            lessons[-1] = f"{lessons[-1]} {line.strip()}"
    return tuple(lessons)


def _is_content(path) -> bool:
    if not path.name.startswith(PREFIX) or not (path / "SKILL.md").is_file():
        return False
    try:
        front, _body = _split(path.name, (path / "SKILL.md").read_text())
    except SkillError:
        return False
    return "makes" in front


def names() -> list[str]:
    return sorted(path.name for path in SKILLS_DIR.iterdir() if _is_content(path))


def load(name) -> Skill:
    path = SKILLS_DIR / name / "SKILL.md"
    if not path.is_file():
        _refuse(name, "has no SKILL.md")
    data = path.read_bytes()
    front, body = _split(name, data.decode())
    if front.get("name") is None:
        _refuse(name, "front matter has no name")
    if front["name"] != name:
        _refuse(name, f"front matter names {front['name']!r}, not the directory")
    return Skill(
        name,
        front.get("description") or "",
        _makes(name, front),
        body,
        _lessons(name, body),
        hashlib.sha256(data).hexdigest(),
    )


def for_kind(kind) -> str:
    for name in names():
        if load(name).makes == kind:
            return name
    raise SkillError(f"no skill makes {kind!r}")
