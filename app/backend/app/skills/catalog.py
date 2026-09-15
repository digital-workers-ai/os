import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.caches import BACKEND_DIR

SKILLS_DIR = BACKEND_DIR / ".claude" / "skills"

PREFIX = "dw-"

MODES = ("draft", "build", "chat")

FRONT_MATTER = re.compile(r"\A---\n(.*?)^---\n", re.DOTALL | re.MULTILINE)

BOLD = re.compile(r"\*\*([a-z]+)\*\*")

NAME = re.compile(r"\Adw-[a-z0-9-]+\Z")

MODES_HEADING = "\n## Modes\n"

LESSONS_HEADING = "\n## Lessons\n"


class SkillError(RuntimeError):
    pass


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    body: str
    lessons: tuple
    modes: tuple
    sha: str


def _file(name: str) -> Path:
    return Path(SKILLS_DIR) / name / "SKILL.md"


def names() -> list[str]:
    directory = Path(SKILLS_DIR)
    if not directory.is_dir():
        return []
    return sorted(
        found.name
        for found in directory.glob(f"{PREFIX}*")
        if (found / "SKILL.md").is_file()
        and MODES_HEADING in (found / "SKILL.md").read_text()
    )


def _lessons(text: str) -> tuple:
    found: list[str] = []
    for line in text.splitlines():
        if line.startswith("- "):
            found.append(line[2:].strip())
        elif line.startswith("  ") and found:
            found[-1] = f"{found[-1]} {line.strip()}"
    return tuple(found)


def _modes(text: str) -> tuple:
    section = text.partition(MODES_HEADING)[2].split("\n## ")[0]
    named = set(BOLD.findall(section))
    return tuple(mode for mode in MODES if mode in named)


def load(name: str) -> Skill:
    file = _file(name) if NAME.match(str(name)) else None
    text = file.read_text() if file and file.is_file() else ""
    if MODES_HEADING not in text:
        raise SkillError(f"no skill named {name!r} — Studio runs {names()}")
    front = FRONT_MATTER.match(text)
    if not front:
        raise SkillError(
            f"{name}: SKILL.md opens with no front matter — nothing says what "
            "the skill makes or how it is called"
        )
    rest = text[front.end() :]
    body, found, lessons = rest.partition(LESSONS_HEADING)
    if not found:
        raise SkillError(
            f"{name}: SKILL.md has no ## Lessons section — the taste agent "
            "appends there, and a run records which corrections were in force"
        )
    return Skill(
        name=name,
        description=str((yaml.safe_load(front[1]) or {}).get("description") or ""),
        body=body.strip(),
        lessons=_lessons(lessons.split("\n## ")[0]),
        modes=_modes(rest),
        sha=hashlib.sha256(text.encode()).hexdigest(),
    )


def sha(name: str) -> str:
    return load(name).sha


def lessons(name: str) -> tuple:
    return load(name).lessons
