import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select

from app import caches
from app.caches import load_mapping
from app.models import CanonicalLink, EntityCanonical, FactCurrent

DEFAULT_RULES = caches.DEFINITIONS_DIR / "rules.yaml"

SEVERITIES = ("high", "medium", "low")

NUMERIC_OPS = frozenset({"gt", "gte", "lt", "lte"})
DATE_OPS = frozenset({"older_than_days", "within_days"})
PRESENCE_OPS = frozenset({"exists", "is_null"})
TEXT_OPS = frozenset(
    {"equals", "not_equals", "contains", "not_contains", "starts_with"}
)

OPERATORS = NUMERIC_OPS | DATE_OPS | PRESENCE_OPS | TEXT_OPS

_ISO_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}")

MAX_EVIDENCE_CHARS = 120


class RuleError(ValueError):
    pass


@dataclass(frozen=True)
class Condition:
    attr: str
    op: str
    operand: object


@dataclass(frozen=True)
class Rule:
    name: str
    label: str
    entity: str
    severity: str
    all_of: tuple = ()
    any_of: tuple = ()

    @property
    def conditions(self) -> tuple:
        return self.all_of + self.any_of


@dataclass(frozen=True)
class Finding:
    rule: str
    label: str
    severity: str
    entity_type: str
    canonical_id: object
    anchor: str
    company: str | None
    evidence: dict

    def as_dict(self) -> dict:
        return {
            "rule": self.rule,
            "label": self.label,
            "severity": self.severity,
            "entity_type": self.entity_type,
            "canonical_id": str(self.canonical_id),
            "anchor": self.anchor,
            "company": self.company,
            "evidence": self.evidence,
        }


class Report:
    def __init__(self) -> None:
        self.unreadable: dict = {}
        self.evaluated = 0

    def cannot_read(self, entity_type: str, attr: str, op: str) -> None:
        key = f"{entity_type}.{attr}/{op}"
        self.unreadable[key] = self.unreadable.get(key, 0) + 1

    def as_dict(self) -> dict:
        return {
            "evaluated": self.evaluated,
            "unreadable": dict(sorted(self.unreadable.items())),
        }


def _as_number(text) -> float | None:
    try:
        value = float(text)
    except (TypeError, ValueError, OverflowError):
        return None
    return value if math.isfinite(value) else None


def _as_datetime(text) -> datetime | None:
    if not isinstance(text, str) or not _ISO_PREFIX.match(text.strip()):
        return None
    try:
        parsed = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def readable(op: str, stored) -> bool:
    if stored is None or op in PRESENCE_OPS or op in TEXT_OPS:
        return True
    if op in NUMERIC_OPS:
        return _as_number(stored) is not None
    return _as_datetime(stored) is not None


def match(op: str, operand, stored, *, now: datetime) -> bool:
    if op == "exists":
        return stored is not None
    if op == "is_null":
        return stored is None
    if stored is None:
        return False

    text = str(stored).strip()
    if op in TEXT_OPS:
        wanted = str(operand).strip().lower()
        haystack = text.lower()
        if op == "equals":
            return haystack == wanted
        if op == "not_equals":
            return haystack != wanted
        if op == "contains":
            return wanted in haystack
        if op == "starts_with":
            return haystack.startswith(wanted)
        return wanted not in haystack

    if op in NUMERIC_OPS:
        value = _as_number(text)
        threshold = _as_number(operand)
        if value is None or threshold is None:
            return False
        if op == "gt":
            return value > threshold
        if op == "gte":
            return value >= threshold
        if op == "lt":
            return value < threshold
        return value <= threshold

    moment = _as_datetime(text)
    days = _as_number(operand)
    if moment is None or days is None:
        return False
    age = (now - moment).total_seconds() / 86400.0
    if op == "older_than_days":
        return age > days
    return 0 <= age <= days


def parse(name: str, body) -> Rule:
    if not isinstance(body, dict):
        raise RuleError(f"rule {name!r} must be a mapping")

    def _conditions(key) -> tuple:
        out = []
        for entry in body.get(key) or []:
            if not isinstance(entry, dict):
                raise RuleError(f"{name}.{key}: each condition must be a mapping")
            attr = entry.get("attr")
            ops = [k for k in entry if k != "attr"]
            if not attr:
                raise RuleError(f"{name}.{key}: a condition names no attr")
            if len(ops) != 1:
                raise RuleError(
                    f"{name}.{key}: condition on {attr!r} carries {len(ops)} "
                    "operators, and a condition must carry exactly one operator"
                )
            out.append(Condition(attr=str(attr), op=str(ops[0]), operand=entry[ops[0]]))
        return tuple(out)

    severity = str(body.get("severity") or "low")
    if severity not in SEVERITIES:
        raise RuleError(f"{name}: severity must be one of {SEVERITIES}")

    return Rule(
        name=name,
        label=str(body.get("label") or name),
        entity=str(body.get("entity") or ""),
        severity=severity,
        all_of=_conditions("all"),
        any_of=_conditions("any"),
    )


def load(path=None) -> dict:
    doc = load_mapping(path or DEFAULT_RULES, RuleError)
    return {str(name): parse(str(name), body) for name, body in doc.items()}


definitions = caches.cached(load)


async def _facts_for(session, entity_type: str) -> dict:
    rows = (
        await session.execute(
            select(FactCurrent.canonical_id, FactCurrent.attr, FactCurrent.value).where(
                FactCurrent.entity_type == entity_type
            )
        )
    ).all()
    out: dict = {}
    for canonical_id, attr, value in rows:
        out.setdefault(canonical_id, {})[attr] = value
    return out


async def _anchors(session, entity_types) -> dict:
    rows = (
        await session.execute(
            select(EntityCanonical.canonical_id, EntityCanonical.anchor_key).where(
                EntityCanonical.entity_type.in_(list(entity_types))
            )
        )
    ).all()
    return dict(rows)


async def _companies(session) -> dict:
    company_name = (
        select(FactCurrent.canonical_id, FactCurrent.value).where(
            FactCurrent.entity_type == "company", FactCurrent.attr == "name"
        )
    ).subquery()
    rows = (
        await session.execute(
            select(CanonicalLink.from_canonical, company_name.c.value).join(
                company_name,
                company_name.c.canonical_id == CanonicalLink.to_canonical,
            )
        )
    ).all()
    return dict(rows)


def _clip(text: str) -> str:
    return text if len(text) <= MAX_EVIDENCE_CHARS else text[:MAX_EVIDENCE_CHARS] + "…"


def _evidence(rule: Rule, facts: dict) -> dict:
    out = {}
    for condition in rule.conditions:
        value = facts.get(condition.attr)
        if condition.op == "exists":
            out[condition.attr] = f"present ({len(str(value))} chars)"
            continue
        out[condition.attr] = None if value is None else _clip(str(value))
    return out


def _hit(condition: Condition, facts: dict, now: datetime) -> bool:
    return match(condition.op, condition.operand, facts.get(condition.attr), now=now)


async def evaluate(session, *, rules=None, now=None, report=None) -> list:
    rules = rules if rules is not None else definitions()
    now = now or datetime.now(UTC)
    report = report if report is not None else Report()

    entity_types = sorted({rule.entity for rule in rules.values()})
    facts_by_type = {
        entity_type: await _facts_for(session, entity_type)
        for entity_type in entity_types
    }
    if not any(facts_by_type.values()):
        return []
    anchors = await _anchors(session, entity_types)
    companies = await _companies(session)

    findings: list[Finding] = []
    for name, rule in sorted(rules.items()):
        entities = facts_by_type[rule.entity]
        for canonical_id, facts in entities.items():
            report.evaluated += 1
            for condition in rule.conditions:
                if not readable(condition.op, facts.get(condition.attr)):
                    report.cannot_read(rule.entity, condition.attr, condition.op)
            if rule.all_of and not all(_hit(c, facts, now) for c in rule.all_of):
                continue
            if rule.any_of and not any(_hit(c, facts, now) for c in rule.any_of):
                continue
            findings.append(
                Finding(
                    rule=name,
                    label=rule.label,
                    severity=rule.severity,
                    entity_type=rule.entity,
                    canonical_id=canonical_id,
                    anchor=anchors.get(canonical_id, ""),
                    company=companies.get(canonical_id),
                    evidence=_evidence(rule, facts),
                )
            )

    order = {severity: index for index, severity in enumerate(SEVERITIES)}
    findings.sort(key=lambda f: (order[f.severity], f.rule, f.anchor))
    return findings
