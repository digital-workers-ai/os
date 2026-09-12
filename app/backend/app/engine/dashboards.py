from dataclasses import dataclass

from app import caches
from app.engine import metrics

DEFAULT_DASHBOARDS = caches.DEFINITIONS_DIR / "dashboards.yaml"

PAGE_KEYS = frozenset({"label", "range", "sections"})
SECTION_KEYS = frozenset({"label", "cards"})


class DashboardError(ValueError):
    pass


def load(path=None):
    return caches.load_mapping(path or DEFAULT_DASHBOARDS, DashboardError)


definitions = caches.cached(load)


@dataclass(frozen=True)
class Section:
    label: str
    cards: tuple[str, ...]


@dataclass(frozen=True)
class Page:
    name: str
    label: str
    range: bool
    sections: tuple[Section, ...]


def _refuse(name, reason):
    raise DashboardError(f"dashboard {name!r}: {reason}")


def _label(name, spec, what):
    label = spec.get("label")
    if not isinstance(label, str):
        _refuse(name, f"{what} is missing a string `label`")
    return label


def _section(name, spec) -> Section:
    if not isinstance(spec, dict):
        _refuse(name, "each section must be a mapping")
    unknown = sorted(set(spec) - SECTION_KEYS)
    if unknown:
        _refuse(
            name, f"unknown section key {unknown[0]!r} — known: {sorted(SECTION_KEYS)}"
        )
    label = _label(name, spec, "section")
    cards = spec.get("cards")
    if (
        not isinstance(cards, list)
        or not cards
        or not all(isinstance(card, str) for card in cards)
    ):
        _refuse(name, f"section {label!r} needs `cards`: a non-empty list of names")
    return Section(label, tuple(cards))


def parse(name, spec) -> Page:
    if not isinstance(spec, dict):
        _refuse(name, "must be a mapping")
    unknown = sorted(set(spec) - PAGE_KEYS)
    if unknown:
        _refuse(name, f"unknown key {unknown[0]!r} — known: {sorted(PAGE_KEYS)}")
    label = _label(name, spec, "page")
    ranged = spec.get("range", False)
    if not isinstance(ranged, bool):
        _refuse(name, f"range {ranged!r} must be true or false")
    sections = spec.get("sections")
    if not isinstance(sections, list) or not sections:
        _refuse(name, "needs `sections`: a non-empty list")
    return Page(
        str(name), label, ranged, tuple(_section(name, entry) for entry in sections)
    )


def pages(defs) -> tuple[Page, ...]:
    return tuple(parse(name, spec) for name, spec in defs.items())


def shape(parsed) -> str:
    if parsed["group_by"]:
        return "series" if parsed["grain"] else "breakdown"
    if parsed["op"]:
        return "ratio"
    return "kpi"


def _card_problems(page, card, seen, metric_defs) -> list[str]:
    prefix = f"dashboards: page {page.name!r} card {card!r}"
    if card in seen:
        return [f"{prefix} appears twice on the same page"]
    seen.add(card)
    if card not in metric_defs:
        return [f"{prefix} names no metric in metrics.yaml"]
    if not page.range:
        return []
    try:
        parsed = metrics.parse_spec(metric_defs[card])
    except metrics.MetricSpecError:
        return []
    if parsed["range_attr"] is None:
        return [
            f"{prefix} cannot be ranged — the page has range: true but the "
            "metric declares no window_attr to range over"
        ]
    return []


def check(defs, metric_defs) -> list[str]:
    problems: list[str] = []
    for name, spec in defs.items():
        try:
            page = parse(name, spec)
        except DashboardError as e:
            problems.append(str(e))
            continue
        seen: set[str] = set()
        for section in page.sections:
            for card in section.cards:
                problems += _card_problems(page, card, seen, metric_defs)
    return problems
