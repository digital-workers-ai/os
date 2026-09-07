import re

from app.caches import DEFINITIONS_DIR, load_mapping
from app.engine import ontology

DEFAULT_DERIVED = DEFINITIONS_DIR / "derived.yaml"

SPEC_KEYS = frozenset({"description", "synonyms", "expression", "via", "filter"})

_OVER_ATTR_RE = re.compile(r"^(SUM|MAX)\((\w+)\.(\w+)\)$")
_COUNT_RE = re.compile(r"^COUNT\((\w+)\)$")


class DerivedError(ValueError):
    pass


def load(path=None) -> dict:
    return load_mapping(path or DEFAULT_DERIVED, DerivedError)


def parse(spec) -> dict:
    unknown = sorted(set(spec) - SPEC_KEYS)
    if unknown:
        raise DerivedError(f"unknown key {unknown[0]!r} — known: {sorted(SPEC_KEYS)}")
    expression = str(spec.get("expression") or "")
    over_attr = _OVER_ATTR_RE.match(expression)
    counted = _COUNT_RE.match(expression)
    if over_attr:
        agg, entity, attr = over_attr.group(1), over_attr.group(2), over_attr.group(3)
    elif counted:
        agg, entity, attr = "COUNT", counted.group(1), ""
    else:
        raise DerivedError(
            f"expression {expression!r} must be SUM(entity.attr), "
            "COUNT(entity) or MAX(entity.attr)"
        )
    return {
        "agg": agg,
        "entity": entity,
        "attr": attr,
        "via": str(spec.get("via") or ""),
        "filter": dict(spec.get("filter") or {}),
    }


def _types(onto, specs) -> dict:
    types: dict = {}
    for entity, attrs in specs.items():
        for attr, spec in attrs.items():
            parsed = parse(spec)
            types.setdefault(entity, {})[attr] = (
                "number"
                if parsed["agg"] in ("SUM", "COUNT")
                else onto.attr_type(parsed["entity"], parsed["attr"])
            )
    return types


def types_for(entity, path=None) -> dict:
    return _types(ontology.load(), load(path)).get(entity, {})


def attrs_of(onto, path=None):
    types = _types(onto, load(path))

    def of(entity: str) -> dict:
        return {**onto.entities[entity].attrs, **types.get(entity, {})}

    return of


def check(onto, path=None) -> list[str]:
    problems: list[str] = []
    for entity, attrs in load(path).items():
        target = onto.entities.get(entity)
        for attr, spec in attrs.items():
            prefix = f"derived {entity}.{attr}: "
            if target is None:
                problems.append(f"{prefix}{entity!r} is not a declared entity")
                continue
            if attr in target.attrs:
                problems.append(f"{prefix}shadows a declared attr of {entity}")
            try:
                parsed = parse(spec)
            except DerivedError as e:
                problems.append(f"{prefix}{e}")
                continue
            source = onto.entities.get(parsed["entity"])
            if source is None:
                problems.append(
                    f"{prefix}{parsed['entity']!r} is not a declared entity"
                )
                continue
            edges = [
                r
                for r in onto.relationships_from(parsed["entity"])
                if r.rel == parsed["via"] and r.to_type == entity
            ]
            if not edges:
                problems.append(
                    f"{prefix}no declared edge {parsed['entity']} "
                    f"{parsed['via']} {entity}"
                )
            problems += _source_problems(prefix, parsed, source)
    return problems


def _source_problems(prefix, parsed, source) -> list[str]:
    problems: list[str] = []
    kind = source.attrs.get(parsed["attr"])
    if parsed["attr"] and kind is None:
        problems.append(f"{prefix}{parsed['attr']!r} is not an attr of {source.name}")
    elif parsed["agg"] == "SUM" and kind != "number":
        problems.append(f"{prefix}SUM over a {kind} attr is a category error")
    elif parsed["agg"] == "MAX" and kind not in ("date", "number"):
        problems.append(f"{prefix}MAX over a {kind} attr is a category error")
    for attr in parsed["filter"]:
        if str(attr) not in source.attrs:
            problems.append(
                f"{prefix}filter attr {attr!r} is not an attr of {source.name}"
            )
    return problems
