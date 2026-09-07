import re

from app.caches import DEFINITIONS_DIR, load_mapping
from app.engine import ontology, transforms
from app.engine.survivorship import FoldedFact

DEFAULT_DERIVED = DEFINITIONS_DIR / "derived.yaml"

SPEC_KEYS = frozenset({"expression", "via", "filter"})

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


def _loaded(path) -> dict:
    try:
        return load(path)
    except DerivedError:
        return {}


def _carries_currency(parsed: dict, money) -> bool:
    return parsed["agg"] == "SUM" and parsed["attr"] in money


def _types(onto, specs) -> dict:
    money = transforms.money_labels()
    types: dict = {}
    for entity, attrs in specs.items():
        for attr, spec in attrs.items():
            try:
                parsed = parse(spec)
            except DerivedError:
                continue
            types.setdefault(entity, {})[attr] = (
                "number"
                if parsed["agg"] in ("SUM", "COUNT")
                else onto.attr_type(parsed["entity"], parsed["attr"])
            )
            if _carries_currency(parsed, money):
                types[entity]["currency"] = "string"
    return types


def types_for(entity, path=None) -> dict:
    return _types(ontology.load(), _loaded(path)).get(entity, {})


def attrs_of(onto, path=None):
    types = _types(onto, _loaded(path))

    def of(entity: str) -> dict:
        return {**onto.entities[entity].attrs, **types.get(entity, {})}

    return of


def check(onto, path=None) -> list[str]:
    try:
        specs = load(path)
    except DerivedError as e:
        return [str(e)]
    money = transforms.money_labels()
    money_targets: set = set()
    problems: list[str] = []
    for entity, attrs in specs.items():
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
            if not _carries_currency(parsed, money):
                continue
            if "currency" in target.attrs:
                problems.append(
                    f"{prefix}the currency this money SUM writes shadows a "
                    f"declared attr of {entity}"
                )
            if entity in money_targets:
                problems.append(
                    f"{prefix}a second money SUM on {entity} writes its "
                    "currency twice — one target carries one currency"
                )
            money_targets.add(entity)
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


def _index(folded) -> tuple:
    values: dict = {}
    newest: dict = {}
    kinds: dict = {}
    for fact in folded:
        values.setdefault(fact.canonical_id, {})[fact.attr] = fact
        newest[fact.canonical_id] = max(
            newest.get(fact.canonical_id, fact.observed_at), fact.observed_at
        )
        kinds[fact.canonical_id] = fact.entity_type
    return values, newest, kinds


def _passes(values: dict, wanted: dict) -> bool:
    for attr, value in wanted.items():
        fact = values.get(str(attr))
        if fact is None or fact.value.casefold() != str(value).casefold():
            return False
    return True


def _greatest(kind):
    if kind == "number":
        return lambda fact: fact.value_num
    return lambda fact: fact.value


def _currencies(values: dict, kept: list) -> set:
    return {values[cid]["currency"].value for cid in kept if "currency" in values[cid]}


def _number_text(value) -> str:
    return str(float(value))


def _derived_fact(target, entity, attr, value, value_num, observed_at) -> FoldedFact:
    return FoldedFact(
        canonical_id=target,
        entity_type=entity,
        attr=attr,
        value=value,
        value_num=value_num,
        source="",
        entity_key=None,
        raw_event_id=None,
        observed_at=observed_at,
        disagreements=0,
    )


def _aggregate(parsed: dict, kind, values: dict, newest: dict, kept: list):
    attr = parsed["attr"]
    carrying = [values[cid][attr] for cid in kept if attr in values[cid]]
    stamps = [fact.observed_at for fact in carrying]
    if parsed["agg"] == "COUNT":
        counted = float(len(kept))
        return _number_text(counted), counted, [newest[cid] for cid in kept]
    if parsed["agg"] == "SUM":
        total = float(sum(fact.value_num for fact in carrying))
        return _number_text(total), total, stamps
    if not carrying:
        return None
    best = max(carrying, key=_greatest(kind))
    return best.value, best.value_num, [best.observed_at]


def compute(specs: dict, onto, folded: list, edges: list, money) -> tuple:
    values, newest, kinds = _index(folded)
    inbound: dict = {}
    for edge in edges:
        inbound.setdefault((edge.to_canonical, edge.rel), []).append(
            edge.from_canonical
        )

    facts: list = []
    refused: list = []
    for entity, attrs in specs.items():
        targets = [cid for cid, kind in kinds.items() if kind == entity]
        for attr, spec in attrs.items():
            parsed = parse(spec)
            kind = onto.attr_type(parsed["entity"], parsed["attr"])
            carries_currency = _carries_currency(parsed, money)
            for target in targets:
                kept = [
                    cid
                    for cid in inbound.get((target, parsed["via"]), [])
                    if kinds.get(cid) == parsed["entity"]
                    and _passes(values[cid], parsed["filter"])
                ]
                spans = _currencies(values, kept) if carries_currency else set()
                if len(spans) > 1:
                    refused.append(
                        {
                            "entity": entity,
                            "attr": attr,
                            "canonical_id": target,
                            "reason": "mixed_currencies",
                        }
                    )
                    continue
                made = _aggregate(parsed, kind, values, newest, kept)
                if made is None:
                    continue
                value, value_num, stamps = made
                observed_at = max(stamps) if stamps else newest[target]
                facts.append(
                    _derived_fact(target, entity, attr, value, value_num, observed_at)
                )
                if stamps and len(spans) == 1:
                    facts.append(
                        _derived_fact(
                            target, entity, "currency", spans.pop(), None, observed_at
                        )
                    )
    return facts, refused
