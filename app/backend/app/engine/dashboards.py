import re
from dataclasses import dataclass

from app import caches
from app.engine import metrics

DEFAULT_DASHBOARDS = caches.DEFINITIONS_DIR / "dashboards.yaml"

PAGE_KEYS = frozenset(
    {"label", "parent", "range", "goals", "findings", "filter", "sections"}
)
SECTION_KEYS = frozenset({"label", "cards"})
TABLE_KEYS = frozenset(
    {"table", "label", "rank", "columns", "window_attr", "limit", "filter"}
)
MAX_LIMIT = 50

_ATTR_RE = re.compile(r"^\w+$")


class DashboardError(ValueError):
    pass


def load(path=None):
    return caches.load_mapping(path or DEFAULT_DASHBOARDS, DashboardError)


definitions = caches.cached(load)


@dataclass(frozen=True)
class TableCard:
    entity: str
    label: str
    rank: str
    columns: tuple[str, ...]
    window_attr: str | None
    limit: int
    filter: dict


@dataclass(frozen=True)
class Section:
    label: str
    cards: tuple[str | TableCard, ...]


@dataclass(frozen=True)
class Page:
    name: str
    label: str
    parent: str | None
    range: bool
    goals: bool
    findings: bool
    filter: dict
    sections: tuple[Section, ...]


def _refuse(name, reason):
    raise DashboardError(f"dashboard {name!r}: {reason}")


def _text(name, spec, key, what) -> str:
    value = spec.get(key)
    if not isinstance(value, str):
        _refuse(name, f"{what} is missing a string `{key}`")
    return value


def _parent(name, spec) -> str | None:
    parent = spec.get("parent")
    if parent is not None and not isinstance(parent, str):
        _refuse(name, f"parent {parent!r} must be a page name")
    return parent


def _flag(name, spec, key) -> bool:
    value = spec.get(key, False)
    if not isinstance(value, bool):
        _refuse(name, f"{key} {value!r} must be true or false")
    return value


def _filter(name, spec, what) -> dict:
    filt = spec.get("filter", {})
    if not isinstance(filt, dict):
        _refuse(name, f"{what} filter must be a mapping of attr → value")
    for attr, value in filt.items():
        if not _ATTR_RE.match(str(attr)):
            _refuse(name, f"{what} filter attr {attr!r} is not a plain attribute name")
        if isinstance(value, bool) or not isinstance(value, str | int | float):
            _refuse(
                name,
                f"{what} filter value {value!r} on {attr!r} must be a string "
                "or a number",
            )
    return dict(filt)


def _columns(name, spec) -> tuple:
    columns = spec.get("columns")
    if (
        not isinstance(columns, list)
        or not columns
        or not all(isinstance(column, str) for column in columns)
    ):
        _refuse(name, "table card needs `columns`: a non-empty list of attr names")
    return tuple(columns)


def _window_attr(name, spec) -> str | None:
    window_attr = spec.get("window_attr")
    if window_attr is not None and not isinstance(window_attr, str):
        _refuse(name, f"table card window_attr {window_attr!r} must be an attr name")
    return window_attr


def _limit(name, spec) -> int:
    limit = spec.get("limit", 10)
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1 <= limit <= MAX_LIMIT
    ):
        _refuse(name, f"table card limit {limit!r} must be a whole number from 1 to 50")
    return limit


def _table(name, spec) -> TableCard:
    unknown = sorted(set(spec) - TABLE_KEYS)
    if unknown:
        _refuse(
            name, f"unknown table card key {unknown[0]!r} — known: {sorted(TABLE_KEYS)}"
        )
    return TableCard(
        _text(name, spec, "table", "table card"),
        _text(name, spec, "label", "table card"),
        _text(name, spec, "rank", "table card"),
        _columns(name, spec),
        _window_attr(name, spec),
        _limit(name, spec),
        _filter(name, spec, "table card"),
    )


def _card(name, card):
    if isinstance(card, str):
        return card
    return _table(name, card)


def _section(name, spec) -> Section:
    if not isinstance(spec, dict):
        _refuse(name, "each section must be a mapping")
    unknown = sorted(set(spec) - SECTION_KEYS)
    if unknown:
        _refuse(
            name, f"unknown section key {unknown[0]!r} — known: {sorted(SECTION_KEYS)}"
        )
    label = _text(name, spec, "label", "section")
    cards = spec.get("cards")
    if (
        not isinstance(cards, list)
        or not cards
        or not all(isinstance(card, str | dict) for card in cards)
    ):
        _refuse(
            name,
            f"section {label!r} needs `cards`: a non-empty list of metric names "
            "or table mappings",
        )
    return Section(label, tuple(_card(name, card) for card in cards))


def parse(name, spec) -> Page:
    if not isinstance(spec, dict):
        _refuse(name, "must be a mapping")
    unknown = sorted(set(spec) - PAGE_KEYS)
    if unknown:
        _refuse(name, f"unknown key {unknown[0]!r} — known: {sorted(PAGE_KEYS)}")
    label = _text(name, spec, "label", "page")
    parent = _parent(name, spec)
    ranged = _flag(name, spec, "range")
    goals = _flag(name, spec, "goals")
    findings = _flag(name, spec, "findings")
    filt = _filter(name, spec, "page")
    sections = spec.get("sections", [])
    if not isinstance(sections, list) or not (sections or goals or findings):
        _refuse(name, "needs `sections`: a non-empty list")
    return Page(
        str(name),
        label,
        parent,
        ranged,
        goals,
        findings,
        filt,
        tuple(_section(name, entry) for entry in sections),
    )


def pages(defs) -> tuple[Page, ...]:
    return tuple(parse(name, spec) for name, spec in defs.items())


def shape(parsed) -> str:
    if parsed["group_by"]:
        return "series" if parsed["grain"] else "breakdown"
    if parsed["op"]:
        return "ratio"
    return "kpi"


def _entity_attrs(attrs_of, entity):
    try:
        return attrs_of(entity)
    except KeyError:
        return None


def _filter_problems(prefix, entity, attrs, filt) -> list[str]:
    return [
        f"{prefix} is filtered on {attr!r}, which is not an attr of {entity}"
        for attr in filt
        if attr not in attrs
    ]


def _metric_problems(page, card, seen, metric_defs, attrs_of) -> list[str]:
    prefix = f"dashboards: page {page.name!r} card {card!r}"
    if card in seen:
        return [f"{prefix} appears twice on the same page"]
    seen.add(card)
    if card not in metric_defs:
        return [f"{prefix} names no metric in metrics.yaml"]
    spec = metric_defs[card]
    entity = str(spec.get("entity")) if isinstance(spec, dict) else ""
    problems: list[str] = []
    attrs = _entity_attrs(attrs_of, entity)
    if attrs is not None:
        problems += _filter_problems(prefix, entity, attrs, page.filter)
    if not page.range:
        return problems
    try:
        parsed = metrics.parse_spec(spec)
    except metrics.MetricSpecError:
        return problems
    if parsed["range_attr"] is None:
        problems.append(
            f"{prefix} cannot be ranged — the page has range: true but the "
            "metric declares no window_attr to range over"
        )
    return problems


def _table_problems(page, card, attrs_of) -> list[str]:
    prefix = f"dashboards: page {page.name!r} table {card.label!r}"
    attrs = _entity_attrs(attrs_of, card.entity)
    if attrs is None:
        return [f"{prefix} ranks {card.entity!r}, which is not a declared entity"]
    problems = [
        f"{prefix} reads {attr!r}, which is not an attr of {card.entity}"
        for attr in dict.fromkeys((card.rank, *card.columns))
        if attr not in attrs
    ]
    problems += _filter_problems(
        prefix, card.entity, attrs, {**page.filter, **card.filter}
    )
    if card.rank in attrs and attrs[card.rank] != "number":
        problems.append(
            f"{prefix} ranks on {card.rank!r}, which is {attrs[card.rank]}, "
            "not a number"
        )
    if card.window_attr is None:
        if page.range:
            problems.append(
                f"{prefix} cannot be ranged — the page has range: true but the "
                "table declares no window_attr to range over"
            )
    elif card.window_attr not in attrs:
        problems.append(
            f"{prefix} windows on {card.window_attr!r}, which is not an attr of "
            f"{card.entity}"
        )
    elif attrs[card.window_attr] != "date":
        problems.append(
            f"{prefix} windows on {card.window_attr!r}, which is "
            f"{attrs[card.window_attr]}, not a date"
        )
    return problems


def _parent_problems(page, parent_of) -> list[str]:
    prefix = f"dashboards: page {page.name!r} parent {page.parent!r}"
    if page.parent is None:
        return []
    if page.parent == page.name:
        return [f"{prefix} is the page itself"]
    if page.parent not in parent_of:
        return [f"{prefix} names no page in dashboards.yaml"]
    if parent_of[page.parent] is not None:
        return [f"{prefix} has a parent of its own — pages nest one level only"]
    return []


def _card_problems(page, metric_defs, attrs_of) -> list[str]:
    problems: list[str] = []
    seen: set[str] = set()
    for section in page.sections:
        for card in section.cards:
            if isinstance(card, str):
                problems += _metric_problems(page, card, seen, metric_defs, attrs_of)
            else:
                problems += _table_problems(page, card, attrs_of)
    return problems


def check(defs, metric_defs, attrs_of) -> list[str]:
    problems: list[str] = []
    pages: list[Page] = []
    for name, spec in defs.items():
        try:
            pages.append(parse(name, spec))
        except DashboardError as e:
            problems.append(str(e))
    parent_of = dict.fromkeys(defs) | {page.name: page.parent for page in pages}
    for page in pages:
        problems += _parent_problems(page, parent_of)
        problems += _card_problems(page, metric_defs, attrs_of)
    return problems
