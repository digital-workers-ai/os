import re
from datetime import date, timedelta
from pathlib import Path

import yaml

from app import caches

DEFAULT_CALENDAR = caches.DEFINITIONS_DIR / "calendar.yaml"

KINDS = ("post", "newsletter", "blog", "image", "carousel")
CADENCES = ("weekly", "fortnightly", "monthly")
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class CalendarError(ValueError):
    pass


def _load(path) -> dict:
    doc = caches.load_mapping(path, CalendarError)
    declared = doc.get("slots")
    if not isinstance(declared, dict):
        raise CalendarError(
            f"{Path(path).name}: `slots` must be a mapping of slot name → slot"
        )
    return declared


def slots() -> dict:
    return _load(DEFAULT_CALENDAR)


def _span(frm, to) -> list[date]:
    return [frm + timedelta(days=n) for n in range((to - frm).days + 1)]


def dates(slot, frm, to) -> list[date]:
    if slot["when"] == "monthly":
        return [day for day in _span(frm, to) if day.day == slot["day"]]
    named = slot.get("days") or [slot["day"]]
    every_week = slot["when"] == "weekly"
    return [
        day
        for day in _span(frm, to)
        if DAYS[day.weekday()] in named
        and (every_week or day.isocalendar().week % 2 == 0)
    ]


def _weekday_problems(prefix, spec) -> list[str]:
    has_day, has_days = "day" in spec, "days" in spec
    if has_day == has_days:
        return [
            f"{prefix}: a {spec['when']} slot names `day` or `days`, one of the two"
        ]
    if has_day:
        if spec["day"] in DAYS:
            return []
        return [f"{prefix}: day {spec['day']!r} is not one of {DAYS}"]
    days = spec["days"]
    if isinstance(days, list) and days and all(day in DAYS for day in days):
        return []
    return [f"{prefix}: days must be a non-empty list from {DAYS}"]


def _monthly_problems(prefix, spec) -> list[str]:
    day = spec.get("day")
    if isinstance(day, int) and not isinstance(day, bool) and 1 <= day <= 28:
        return []
    return [
        f"{prefix}: a monthly slot names `day` as a whole number from 1 to 28, "
        f"not {day!r}"
    ]


def _slot_problems(name, spec, skills) -> list[str]:
    prefix = f"calendar.yaml: slot {name!r}"
    if not isinstance(spec, dict):
        return [f"{prefix} must be a mapping"]
    problems: list[str] = []
    kind = spec.get("kind")
    if kind not in KINDS:
        problems.append(f"{prefix}: kind {kind!r} is not one of {KINDS}")
    skill = spec.get("skill")
    if not isinstance(skill, str) or not skill.startswith("dw-"):
        problems.append(f"{prefix}: skill {skill!r} must be a dw- skill name")
    elif skills is not None and skill not in skills:
        problems.append(
            f"{prefix}: skill {skill!r} is not a content skill — known: "
            f"{sorted(skills)}"
        )
    when = spec.get("when")
    if when not in CADENCES:
        problems.append(f"{prefix}: when {when!r} is not one of {CADENCES}")
    elif when == "monthly":
        problems += _monthly_problems(prefix, spec)
    else:
        problems += _weekday_problems(prefix, spec)
    time = spec.get("time")
    if not isinstance(time, str) or not TIME.match(time):
        problems.append(f"{prefix}: time {time!r} must be a quoted HH:MM")
    theme = spec.get("theme")
    if not isinstance(theme, str) or not theme.strip():
        problems.append(
            f"{prefix}: theme must be a non-empty sentence the skill can act on"
        )
    for key in ("look", "ratio"):
        if key in spec and not isinstance(spec[key], str):
            problems.append(f"{prefix}: {key} {spec[key]!r} must be a string")
    return problems


def check(path=None, skills=None) -> list[str]:
    path = Path(path or DEFAULT_CALENDAR)
    if not path.is_file():
        return [f"{path.name} is missing — the marketer fills its slots every morning"]
    try:
        declared = _load(path)
    except CalendarError as e:
        return [str(e)]
    except yaml.YAMLError as e:
        return [f"{path.name} does not parse — {e}"]
    problems: list[str] = []
    for name, spec in declared.items():
        problems += _slot_problems(name, spec, skills)
    return problems
