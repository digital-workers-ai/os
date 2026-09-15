import re

from app import caches

DEFAULT_CALENDAR = caches.DEFINITIONS_DIR / "calendar.yaml"

KINDS = ("newsletter", "post", "blog", "video", "ad")

CADENCES = ("weekly", "fortnightly", "monthly", "reactive")

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

THEMES = ("brand", "competitor")

LAST_DAY_EVERY_MONTH_HAS = 28

CLOCK_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class CalendarError(ValueError):
    pass


def load(path=None) -> dict:
    return caches.load_mapping(path or DEFAULT_CALENDAR, CalendarError)


definitions = caches.cached(load)


def slots() -> dict:
    return definitions()["slots"]


def _weekdays(slot) -> list:
    named = slot.get("days")
    if isinstance(named, list):
        return named
    day = slot.get("day")
    return [day] if day is not None else []


def _cadence_problems(prefix, when, slot) -> list[str]:
    if when == "reactive":
        if not slot.get("cap_per_week"):
            return [
                f"{prefix}: reacts but names no cap_per_week — a slot that "
                "fires on news with no ceiling is a feed, not a schedule"
            ]
        return []
    if when == "monthly":
        day = slot.get("day")
        if not isinstance(day, int) or not 1 <= day <= LAST_DAY_EVERY_MONTH_HAS:
            return [
                f"{prefix}: day {day!r} is not between 1 and "
                f"{LAST_DAY_EVERY_MONTH_HAS} — a later one skips February"
            ]
        return []
    named = _weekdays(slot)
    problems: list[str] = []
    if not named:
        problems.append(
            f"{prefix}: {when} and names no weekday — the slot would never "
            "land on a date"
        )
    return problems + [
        f"{prefix}: day {day!r} is not a weekday — known: {list(WEEKDAYS)}"
        for day in named
        if day not in WEEKDAYS
    ]


def check(path=None) -> list[str]:
    try:
        doc = load(path)
    except CalendarError as e:
        return [str(e)]
    entries = doc.get("slots")
    if not isinstance(entries, dict):
        return [
            "calendar.yaml: `slots:` must be a mapping of slot name to slot — "
            "a schedule with no slots fills nothing"
        ]

    problems: list[str] = []
    for name, slot in sorted(entries.items()):
        prefix = f"slot {name!r}"
        if not isinstance(slot, dict):
            problems.append(f"{prefix} must be a mapping")
            continue
        kind = slot.get("kind")
        if kind not in KINDS:
            problems.append(
                f"{prefix}: kind {kind!r} is not something Studio makes — "
                f"known: {list(KINDS)}"
            )
        theme = slot.get("theme")
        if theme not in THEMES:
            problems.append(
                f"{prefix}: theme {theme!r} names no source of material — "
                f"known: {list(THEMES)}"
            )
        at = slot.get("time")
        if at is not None and not CLOCK_TIME.match(str(at)):
            problems.append(
                f"{prefix}: time {at!r} is not a 24-hour HH:MM — quote it, or "
                "YAML reads 06:00 as a number"
            )
        when = slot.get("when")
        if when not in CADENCES:
            problems.append(
                f"{prefix}: when {when!r} is not a cadence — known: {list(CADENCES)}"
            )
            continue
        problems += _cadence_problems(prefix, when, slot)
    return problems
