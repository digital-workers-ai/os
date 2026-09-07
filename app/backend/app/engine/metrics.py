import math
import re
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select

from app.caches import DEFINITIONS_DIR, load_mapping
from app.engine import derived, ontology, transforms
from app.enrichment import vocabulary
from app.models import (
    CanonicalLink,
    EnrichedFact,
    EntityCanonical,
    FactCurrent,
    MetricSnapshot,
)

DEFAULT_METRICS = DEFINITIONS_DIR / "metrics.yaml"

_AGG_RE = re.compile(r"^(COUNT_DISTINCT|SUM|AVG|COUNT)\((\w+)\)$")
_ATTR_RE = re.compile(r"^\w+$")
PATH_RE = re.compile(r"^(\w+)\.(\w+)$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")

SPEC_KEYS = frozenset(
    {
        "label",
        "description",
        "synonyms",
        "entity",
        "expression",
        "filter",
        "source",
        "inferred",
        "reading",
        "population",
        "op",
        "terms",
        "group_by",
        "grain",
        "window_days",
        "window_attr",
        "window_direction",
    }
)

TERM_KEYS = frozenset({"expression", "filter", "source", "entity"})

GRAINS = ("day", "week", "month", "quarter", "year")

TRAILING, FORWARD = "trailing", "forward"

DIRECTIONS = (FORWARD, TRAILING)

ID_CHUNK = 8000

READ_POPULATION = "entities read under the current vocabulary"
ALL_POPULATION = "all entities, including those never read"


class MetricSpecError(ValueError):
    pass


def load_definitions(path=None) -> dict:
    return load_mapping(path or DEFAULT_METRICS, MetricSpecError)


def money_labels(path=None) -> set:
    return {
        label
        for label, fn in transforms.load_map(path).items()
        if fn == "normalize_money"
    }


def _parse_expression(expression) -> dict:
    match = _AGG_RE.match(str(expression or ""))
    if not match:
        raise MetricSpecError(f"bad expression: {expression!r}")
    return {"agg": match.group(1), "operand": match.group(2)}


def parse_terms(spec) -> tuple:
    if "terms" not in spec:
        entry = _parse_expression(spec.get("expression"))
        entry["filter"] = spec.get("filter")
        return [entry], None
    op = spec.get("op")
    if op != "/":
        raise MetricSpecError(f"op {op!r} is not supported — the only ratio op is '/'")
    parsed = []
    for term in spec["terms"]:
        unknown = sorted(set(term) - TERM_KEYS)
        if unknown:
            raise MetricSpecError(
                f"unknown key {unknown[0]!r} on a term — known: {sorted(TERM_KEYS)}"
            )
        entry = _parse_expression(term.get("expression"))
        entry["filter"] = term["filter"] if "filter" in term else spec.get("filter")
        if "source" in term:
            entry["source"] = str(term["source"])
        if "entity" in term:
            entry["entity"] = str(term["entity"])
        parsed.append(entry)
    if len(parsed) != 2:
        raise MetricSpecError(f"`terms:` takes exactly two terms — got {len(parsed)}")
    return parsed, op


def _validate_filter(filt) -> None:
    if filt is None:
        return
    if not isinstance(filt, dict):
        raise MetricSpecError("filter must be a mapping of attr → value")
    for attr in filt:
        if not _ATTR_RE.match(str(attr)):
            raise MetricSpecError(f"filter attr {attr!r} is not a plain attribute name")


def _validate_enriched_term(spec, term, reading) -> None:
    fields = {field.name: field for field in reading.fields}
    entity = str(term.get("entity") or spec["entity"])
    if entity != reading.entity:
        raise MetricSpecError(
            f"reading {reading.name!r} reads {reading.entity!r} — an enriched "
            f"term over {entity!r} counts a thing the reading never read"
        )
    if term["agg"] in ("SUM", "AVG"):
        raise MetricSpecError(
            f"{term['agg']}({term['operand']}) over an inferred label is a "
            "category error — a label has no magnitude. Only COUNT and "
            "COUNT_DISTINCT mean anything over a closed vocabulary"
        )
    if term["operand"] != "entity" and term["operand"] not in fields:
        raise MetricSpecError(
            f"{term['operand']!r} is not a field of reading {reading.name!r} — "
            f"known: {sorted(fields)}"
        )
    for attr, cond in (term["filter"] or {}).items():
        field = fields.get(str(attr))
        if field is None:
            raise MetricSpecError(
                f"filter attr {attr!r} is not a field of reading "
                f"{reading.name!r} — known: {sorted(fields)}"
            )
        banned = (
            set(cond) & {"contains", "not_contains", "gte"}
            if isinstance(cond, dict)
            else set()
        )
        if banned:
            raise MetricSpecError(
                f"filter on {attr!r} uses {sorted(banned)} — substring and "
                "threshold operators are meaningless over a closed label set"
            )
        wanted = cond.get("not_equals") if isinstance(cond, dict) else cond
        if wanted is not None and str(wanted) not in field.labels:
            raise MetricSpecError(
                f"{attr}={wanted!r} is not a label of {reading.name}.{attr} — "
                f"known: {list(field.labels)}"
            )


def parse_spec(spec) -> dict:
    if not isinstance(spec, dict):
        raise MetricSpecError("metric spec must be a mapping")
    unknown = sorted(set(spec) - SPEC_KEYS)
    if unknown:
        raise MetricSpecError(
            f"unknown key {unknown[0]!r} — known: {sorted(SPEC_KEYS)}"
        )
    terms, op = parse_terms(spec)
    if not spec.get("entity"):
        raise MetricSpecError("metric is missing `entity`")
    for term in terms:
        _validate_filter(term["filter"])
        term["source"] = str(term.get("source") or spec.get("source") or "canonical")
        if term["source"] not in ("canonical", "enriched"):
            raise MetricSpecError(
                f"source {term['source']!r} must be `canonical` or `enriched`"
            )
        if term["agg"] == "COUNT_DISTINCT" and term["source"] != "enriched":
            raise MetricSpecError(
                "COUNT_DISTINCT is only defined over enriched readings — a "
                "canonical attr holds one current value per entity, so COUNT "
                "already counts distinct entities"
            )
    group_by = spec.get("group_by")
    if group_by is not None:
        if len({term.get("entity") or spec["entity"] for term in terms}) > 1:
            raise MetricSpecError(
                "group_by over a cross-entity ratio is not defined — the two "
                "terms count different kinds of thing"
            )
        if not (_ATTR_RE.match(str(group_by)) or PATH_RE.match(str(group_by))):
            raise MetricSpecError(
                f"group_by {group_by!r} must be `attr` or `entity.attr`"
            )

    if op:
        signatures = [
            (
                term.get("entity") or spec["entity"],
                term["agg"],
                term["operand"],
                term["filter"],
                term["source"],
            )
            for term in terms
        ]
        if signatures[0] == signatures[1]:
            raise MetricSpecError(
                "degenerate ratio — both terms measure the same thing, so the "
                "value can only ever be 1"
            )

    if any(term["source"] == "enriched" for term in terms):
        if spec.get("inferred") is not True:
            raise MetricSpecError(
                "a metric touching inferred labels must declare `inferred: "
                "true` — without the flag an estimate is shaped exactly like "
                "a measurement"
            )
        reading_name = str(spec.get("reading") or "")
        readings = vocabulary.load()
        if reading_name not in readings:
            raise MetricSpecError(
                f"reading {reading_name!r} is not declared in enrichment.yaml "
                f"— known: {sorted(readings)}"
            )
        reading = readings[reading_name]
        for term in terms:
            if term["source"] == "enriched":
                _validate_enriched_term(spec, term, reading)
        if spec.get("window_days"):
            raise MetricSpecError(
                "window_days on an inferred metric is not applied — the "
                "enriched population is selected by reading and vocabulary, "
                "not by date, and the receipt would claim a window that never "
                "ran. Drop the window, or measure the canonical side."
            )
        population = str(spec.get("population") or "read")
        if population not in ("read", "all"):
            raise MetricSpecError(f"population {population!r} must be `read` or `all`")
        fields = {field.name: field for field in reading.fields}
        if str(group_by) in fields and fields[str(group_by)].kind == "many_of":
            raise MetricSpecError(
                f"group_by {group_by!r} is a many_of field — one entity carries "
                "several labels, so buckets would not sum to the total"
            )
    elif spec.get("inferred"):
        raise MetricSpecError(
            "`inferred: true` on a metric that touches no reading — the flag "
            "says the number came from a model, and this one did not"
        )

    grain = spec.get("grain")
    if grain is not None:
        if group_by is None:
            raise MetricSpecError(
                "grain without group_by — a grain buckets a breakdown over a "
                "date, and there is no breakdown"
            )
        if str(grain) not in GRAINS:
            raise MetricSpecError(f"grain {grain!r} must be one of {list(GRAINS)}")

    window = None
    window_days = spec.get("window_days")
    direction = spec.get("window_direction")
    if window_days is not None:
        if not isinstance(window_days, int) or window_days <= 0:
            raise MetricSpecError(
                f"window_days {window_days!r} must be a positive integer"
            )
        if not spec.get("window_attr"):
            raise MetricSpecError(
                "window_days needs window_attr — the business-time attr the "
                "window is measured on"
            )
        if direction is not None and str(direction) not in DIRECTIONS:
            raise MetricSpecError(
                f"window_direction {direction!r} must be one of {sorted(DIRECTIONS)}"
            )
        window = {
            "days": window_days,
            "attr": str(spec["window_attr"]),
            "direction": str(direction or TRAILING),
        }
    elif direction is not None:
        raise MetricSpecError(
            "window_direction without window_days — a direction with no span "
            "does not describe a window"
        )

    return {
        "terms": terms,
        "op": op,
        "inferred": bool(spec.get("inferred")),
        "group_by": str(group_by) if group_by is not None else None,
        "grain": str(grain) if grain is not None else None,
        "window": window,
    }


def window_bounds(window_days, direction, now) -> tuple:
    span = timedelta(days=int(window_days) - 1)
    if direction == FORWARD:
        return now.date().isoformat(), (now + span).date().isoformat()
    return (now - span).date().isoformat(), now.date().isoformat()


def _bucket(value, grain) -> str | None:
    try:
        day = date.fromisoformat(str(value)[:10])
    except ValueError:
        return None
    if grain == "day":
        return day.isoformat()
    if grain == "week":
        year, week, _weekday = day.isocalendar()
        return f"{year}-W{week:02d}"
    if grain == "month":
        return f"{day:%Y-%m}"
    if grain == "quarter":
        return f"{day.year}-Q{(day.month - 1) // 3 + 1}"
    return str(day.year)


def validate_dimensions(spec, onto, attrs_of) -> list[str]:
    problems: list[str] = []
    entity = str(spec.get("entity"))
    attrs = attrs_of(entity)
    group_by = spec.get("group_by")
    grain = spec.get("grain")
    kind = None
    if spec.get("inferred"):
        reading = vocabulary.load()[str(spec.get("reading") or "")]
        if str(group_by) in {field.name for field in reading.fields}:
            group_by = None
    if group_by:
        path = PATH_RE.match(str(group_by))
        if path:
            target, attr = path.group(1), path.group(2)
            edges = [r for r in onto.relationships_from(entity) if r.to_type == target]
            safe = [r for r in edges if r.cardinality in ontology.SAFE_FOR_GROUP_BY]
            if not edges:
                problems.append(
                    f"group_by {group_by!r} walks no declared edge from "
                    f"{entity} to {target}"
                )
            elif not safe:
                problems.append(
                    f"group_by {group_by!r} walks a {edges[0].cardinality} edge "
                    "— a breakdown over a fan-out edge double-counts by "
                    "construction"
                )
            elif attr not in attrs_of(target):
                problems.append(
                    f"group_by {group_by!r} — {attr!r} is not an attr of {target}"
                )
            else:
                kind = attrs_of(target)[attr]
        elif str(group_by) not in attrs:
            problems.append(f"group_by {group_by!r} is not an attr of {entity}")
        else:
            kind = attrs[str(group_by)]
    if kind == "date":
        if not grain:
            problems.append(
                f"group_by {group_by!r} is a date — a breakdown over a date needs grain"
            )
    elif kind is not None and grain:
        problems.append(f"grain {grain!r} on {group_by!r}, which is {kind}, not a date")
    window_attr = spec.get("window_attr")
    if window_attr:
        if str(window_attr) not in attrs:
            problems.append(f"window_attr {window_attr!r} is not an attr of {entity}")
        elif attrs[str(window_attr)] != "date":
            problems.append(
                f"window_attr {window_attr!r} is {attrs[str(window_attr)]}, not a date"
            )
    return problems


async def _in_chunks(session, ids, build) -> list:
    ordered = list(ids)
    rows: list = []
    for start in range(0, len(ordered), ID_CHUNK):
        rows.extend(
            (await session.execute(build(ordered[start : start + ID_CHUNK]))).all()
        )
    return rows


async def _ids_for(session, entity_type: str, filt, window) -> tuple:
    notes: dict = {}
    ids = {
        r[0]
        for r in (
            await session.execute(
                select(EntityCanonical.canonical_id).where(
                    EntityCanonical.entity_type == entity_type
                )
            )
        ).all()
    }
    notes["population_size"] = len(ids)
    if window:
        inside, bad = set(), 0
        rows = (
            await session.execute(
                select(FactCurrent.canonical_id, FactCurrent.value).where(
                    FactCurrent.attr == window["attr"],
                    FactCurrent.entity_type == entity_type,
                )
            )
        ).all()
        for canonical_id, value in rows:
            text = str(value).strip()
            if not _DATE_RE.match(text):
                bad += 1
                continue
            if window["from"] <= text[:10] <= window["to"]:
                inside.add(canonical_id)
        if bad:
            notes["window_bad_values"] = bad
        ids &= inside
    for attr, value in (filt or {}).items():
        if not ids:
            break

        def build(chunk, attr=attr, value=value):
            return select(FactCurrent.canonical_id).where(
                FactCurrent.attr == str(attr),
                func.lower(FactCurrent.value) == str(value).lower(),
                FactCurrent.canonical_id.in_(chunk),
            )

        ids &= {r[0] for r in await _in_chunks(session, ids, build)}
    return ids, notes


async def _enriched_ids(session, entity_type, filt, reading, population) -> tuple:
    notes: dict = {}
    rows = (
        await session.execute(
            select(EnrichedFact.canonical_id, EnrichedFact.vocabulary_sha)
            .join(
                EntityCanonical,
                EntityCanonical.canonical_id == EnrichedFact.canonical_id,
            )
            .where(
                EnrichedFact.reading == reading.name,
                EntityCanonical.entity_type == entity_type,
            )
            .distinct()
        )
    ).all()
    read_ids = {cid for cid, sha in rows if sha == reading.sha}
    stale = {cid for cid, sha in rows if sha != reading.sha} - read_ids

    if population == "all":
        ids = {
            r[0]
            for r in (
                await session.execute(
                    select(EntityCanonical.canonical_id).where(
                        EntityCanonical.entity_type == entity_type
                    )
                )
            ).all()
        }
        notes["population"] = ALL_POPULATION
    else:
        ids = set(read_ids)
        notes["population"] = READ_POPULATION
    if stale:
        notes["read_under_a_retired_vocabulary"] = len(stale)

    for attr, cond in (filt or {}).items():
        if not ids:
            break
        wanted = cond.get("not_equals") if isinstance(cond, dict) else cond
        negated = isinstance(cond, dict) and "not_equals" in cond

        def build(chunk, attr=attr, wanted=wanted):
            return select(EnrichedFact.canonical_id).where(
                EnrichedFact.reading == reading.name,
                EnrichedFact.vocabulary_sha == reading.sha,
                EnrichedFact.attr == str(attr),
                func.lower(EnrichedFact.value) == str(wanted).lower(),
                EnrichedFact.canonical_id.in_(chunk),
            )

        hits = {r[0] for r in await _in_chunks(session, ids, build)}
        ids = (ids - hits) if negated else (ids & hits)
    return ids, notes


async def _currencies(session, ids: set) -> set:
    if not ids:
        return set()
    rows = await _in_chunks(
        session,
        ids,
        lambda chunk: (
            select(FactCurrent.value)
            .where(FactCurrent.canonical_id.in_(chunk), FactCurrent.attr == "currency")
            .distinct()
        ),
    )
    return {r[0] for r in rows}


async def _aggregate(session, ids: set, agg: str, operand: str, money: set) -> tuple:
    notes: dict = {}
    if agg == "COUNT" and operand == "entity":
        return len(ids), notes
    if not ids:
        return (None if agg == "AVG" else 0), notes

    if operand in money:
        currencies = await _currencies(session, ids)
        if len(currencies) > 1:
            notes["mixed_currencies"] = sorted(currencies)
            notes["note"] = (
                f"{operand} spans {sorted(currencies)} — refusing to aggregate "
                "across currencies. FX conversion is a named bet, not a "
                "silent sum."
            )
            return None, notes

    if agg == "COUNT":
        rows = await _in_chunks(
            session,
            ids,
            lambda chunk: select(FactCurrent.canonical_id).where(
                FactCurrent.canonical_id.in_(chunk), FactCurrent.attr == operand
            ),
        )
        if len(rows) < len(ids):
            notes["entities_without_attr"] = len(ids) - len(rows)
        return len(rows), notes

    rows = await _in_chunks(
        session,
        ids,
        lambda chunk: select(FactCurrent.value_num).where(
            FactCurrent.canonical_id.in_(chunk),
            FactCurrent.attr == operand,
            FactCurrent.value_num.is_not(None),
        ),
    )
    values = [row[0] for row in rows]
    if len(values) < len(ids):
        notes["entities_without_attr"] = len(ids) - len(values)
    notes["values_aggregated"] = len(values)
    if agg == "SUM":
        return round(sum(values), 2), notes
    if not values:
        return None, notes
    return round(sum(values) / len(values), 2), notes


async def _aggregate_enriched(session, ids, agg, operand, reading) -> tuple:
    notes: dict = {}
    if not ids:
        return 0, notes
    if operand == "entity":
        return len(ids), notes

    rows = await _in_chunks(
        session,
        ids,
        lambda chunk: select(
            EnrichedFact.canonical_id, EnrichedFact.quote_verified
        ).where(
            EnrichedFact.reading == reading.name,
            EnrichedFact.vocabulary_sha == reading.sha,
            EnrichedFact.attr == operand,
            EnrichedFact.canonical_id.in_(chunk),
        ),
    )
    unverified = sum(1 for _cid, verified in rows if not verified)
    if unverified:
        notes["unverified_quotes"] = unverified
    if agg == "COUNT_DISTINCT":
        return len({cid for cid, _verified in rows}), notes
    return len(rows), notes


def _combine(left, right):
    if left is None or not right:
        return None
    return round(left / right, 4)


async def _producers(session, reading, counted) -> list:
    stamps = await _in_chunks(
        session,
        counted,
        lambda chunk: (
            select(EnrichedFact.model, EnrichedFact.prompt_version)
            .where(
                EnrichedFact.reading == reading.name,
                EnrichedFact.vocabulary_sha == reading.sha,
                EnrichedFact.canonical_id.in_(chunk),
            )
            .distinct()
        ),
    )
    return sorted({f"{model}@{version}" for model, version in stamps})


async def _measure(session, spec, terms, op, money, window, term_ids=None) -> dict:
    reading = None
    if any(term["source"] == "enriched" for term in terms):
        reading = vocabulary.load()[str(spec.get("reading"))]
        population = str(spec.get("population") or "read")

    values, notes_all, entities, measured = [], {}, 0, []
    for index, term in enumerate(terms):
        entity_type = str(term.get("entity") or spec["entity"])
        if term_ids is not None:
            ids, notes = term_ids[index], {}
            value, agg_notes = await _aggregate_bucket(
                session, ids, term, reading, money
            )
        elif term["source"] == "enriched":
            ids, notes = await _enriched_ids(
                session, entity_type, term["filter"], reading, population
            )
            value, agg_notes = await _aggregate_enriched(
                session, ids, term["agg"], term["operand"], reading
            )
        else:
            ids, notes = await _ids_for(session, entity_type, term["filter"], window)
            value, agg_notes = await _aggregate(
                session, ids, term["agg"], term["operand"], money
            )
        measured.append(ids)
        notes_all.update(notes)
        notes_all.update(agg_notes)
        entities = max(entities, len(ids))
        values.append(value)

    value = _combine(values[0], values[1]) if op else values[0]
    result = {"value": value, "entities": entities, **notes_all}
    if reading is not None:
        result["inferred"] = True
        result["reading"] = reading.name
        result["vocabulary_sha"] = reading.sha[:12]
        result["produced_by"] = await _producers(
            session, reading, set().union(*measured)
        )
    if entities == 0:
        result["note"] = "no entities matched — no data"
    result["_term_ids"] = measured
    return result


async def _aggregate_bucket(session, ids, term, reading, money) -> tuple:
    if term["source"] == "enriched":
        return await _aggregate_enriched(
            session, ids, term["agg"], term["operand"], reading
        )
    return await _aggregate(session, ids, term["agg"], term["operand"], money)


async def _group_map(session, onto, entity_type, group_by, reading) -> tuple:
    path = PATH_RE.match(group_by)
    if not path:
        if reading is not None and group_by in {f.name for f in reading.fields}:
            query = select(EnrichedFact.canonical_id, EnrichedFact.value).where(
                EnrichedFact.attr == group_by,
                EnrichedFact.reading == reading.name,
                EnrichedFact.vocabulary_sha == reading.sha,
            )
        else:
            query = select(FactCurrent.canonical_id, FactCurrent.value).where(
                FactCurrent.attr == group_by,
                FactCurrent.entity_type == entity_type,
            )
        return dict((await session.execute(query)).all()), None

    target_type, attr = path.group(1), path.group(2)
    edges = [
        r
        for r in onto.relationships_from(entity_type)
        if r.to_type == target_type and r.cardinality in ontology.SAFE_FOR_GROUP_BY
    ]
    if not edges:
        raise MetricSpecError(
            f"group_by {group_by!r} walks no declared edge from {entity_type} "
            f"to {target_type} with a cardinality that cannot fan out"
        )
    rel = edges[0].rel
    links = (
        await session.execute(
            select(CanonicalLink.from_canonical, CanonicalLink.to_canonical).where(
                CanonicalLink.rel == rel
            )
        )
    ).all()
    values = dict(
        (
            await session.execute(
                select(FactCurrent.canonical_id, FactCurrent.value).where(
                    FactCurrent.attr == attr,
                    FactCurrent.entity_type == target_type,
                )
            )
        ).all()
    )
    return {source: values[target] for source, target in links if target in values}, rel


async def _breakdown(session, onto, spec, parsed, money, window, term_ids) -> dict:
    reading = None
    if parsed["inferred"]:
        reading = vocabulary.load()[str(spec.get("reading"))]
    mapping, via = await _group_map(
        session, onto, str(spec["entity"]), parsed["group_by"], reading
    )
    grain = parsed["grain"]
    measured = set().union(*term_ids)
    buckets: dict = {}
    unbucketed = 0
    for canonical_id, value in mapping.items():
        if canonical_id not in measured:
            continue
        key = _bucket(value, grain) if grain else value
        if key is None:
            unbucketed += 1
            continue
        buckets.setdefault(key, set()).add(canonical_id)

    out: dict = {"group_by": parsed["group_by"], "breakdown": {}}
    for key in sorted(buckets):
        bucket = await _measure(
            session,
            spec,
            parsed["terms"],
            parsed["op"],
            money,
            window,
            term_ids=[ids & buckets[key] for ids in term_ids],
        )
        out["breakdown"][key] = bucket["value"]
    if grain:
        out["grain"] = grain
    if via:
        out["group_by_via"] = via
    ungrouped = len(measured) - sum(len(ids) for ids in buckets.values())
    if ungrouped > 0:
        out["ungrouped_entities"] = ungrouped
    if unbucketed:
        out["group_bad_values"] = unbucketed
    return out


async def evaluate_definitions(session, defs: dict, now=None) -> dict:
    onto = ontology.load()
    money = money_labels()
    now = now or datetime.now(UTC)
    out: dict = {}
    for name, spec in defs.items():
        label = spec.get("label", name) if isinstance(spec, dict) else name
        try:
            parsed = parse_spec(spec)
            window = parsed["window"]
            if window:
                low, high = window_bounds(window["days"], window["direction"], now)
                window = {**window, "from": low, "to": high}
            result = await _measure(
                session, spec, parsed["terms"], parsed["op"], money, window
            )
            term_ids = result.pop("_term_ids")
            result["label"] = label
            result["entity"] = spec.get("entity")
            if window:
                result["window_days"] = window["days"]
                result["window_direction"] = window["direction"]
                result["window_from"] = window["from"]
                result["window_to"] = window["to"]
            if parsed["group_by"]:
                result.update(
                    await _breakdown(
                        session, onto, spec, parsed, money, window, term_ids
                    )
                )
            out[name] = result
        except MetricSpecError as e:
            out[name] = {"error": str(e), "label": label}
        except Exception as e:
            out[name] = {"error": f"{type(e).__name__}: {e}", "label": label}
            try:
                await session.rollback()
            except Exception:
                pass
    return out


async def evaluate(session, now=None) -> dict:
    return await evaluate_definitions(session, load_definitions(), now=now)


async def record_snapshots(session) -> int:
    values = await evaluate(session)
    written = 0
    for name, result in values.items():
        if "error" in result:
            continue
        value = result.get("value")
        if isinstance(value, float) and not math.isfinite(value):
            continue
        if not result.get("entities"):
            value = None
        vocabulary_sha = None
        if result.get("inferred"):
            vocabulary_sha = vocabulary.load()[result["reading"]].sha
        produced_by = result.get("produced_by")
        session.add(
            MetricSnapshot(
                metric=name,
                value=value,
                entities=result.get("entities", 0),
                inferred=bool(result.get("inferred")),
                vocabulary_sha=vocabulary_sha,
                produced_by=", ".join(produced_by) if produced_by else None,
            )
        )
        written += 1
    await session.flush()
    return written


async def history(session, metric: str, limit: int = 500) -> dict:
    rows = list(
        reversed(
            (
                await session.execute(
                    select(MetricSnapshot)
                    .where(MetricSnapshot.metric == metric)
                    .order_by(
                        MetricSnapshot.recorded_at.desc(), MetricSnapshot.id.desc()
                    )
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
    )
    runs: list = []
    previous = object()
    for row in rows:
        key = (row.vocabulary_sha, row.produced_by) if row.inferred else (None, None)
        point = {
            "value": row.value,
            "entities": row.entities,
            "recorded_at": row.recorded_at.isoformat(),
        }
        if key == previous:
            runs[-1]["points"].append(point)
            continue
        previous = key
        runs.append(
            {
                "inferred": bool(row.inferred),
                "vocabulary_sha": (row.vocabulary_sha or "")[:12] or None,
                "produced_by": row.produced_by,
                "points": [point],
            }
        )
    return {
        "metric": metric,
        "runs": runs,
        "comparable": len(runs) <= 1,
        "breaks": max(0, len(runs) - 1),
        "inferred": any(run["inferred"] for run in runs),
    }


def _mapped_pairs(specs, entity, attr) -> set:
    spec = (specs.get(entity) or {}).get(attr)
    if spec is None:
        return {(entity, attr)}
    parsed = derived.parse(spec)
    named = [*parsed["filter"], *([parsed["attr"]] if parsed["attr"] else [])]
    return {(parsed["entity"], str(name)) for name in named}


def provenance(defs: dict, lines) -> dict:
    by_entity_label: dict = {}
    for line in lines:
        by_entity_label.setdefault((line.entity, line.label), []).append(line)
    specs = derived.load()

    out: dict = {}
    for name, spec in defs.items():
        try:
            parsed = parse_spec(spec)
        except MetricSpecError:
            continue
        wanted: set = set()
        inferred_from = None
        for term in parsed["terms"]:
            entity = term.get("entity") or spec.get("entity")
            if term["source"] == "enriched":
                reading = vocabulary.load()[str(spec.get("reading"))]
                inferred_from = inferred_from or {
                    "reading": reading.name,
                    "reads": f"{reading.entity}.{reading.input_attr}",
                    "vocabulary": reading.origin,
                    "vocabulary_sha": reading.sha[:12],
                    "fields": [],
                }
                inferred_from["fields"] = sorted(
                    set(inferred_from["fields"])
                    | {
                        field.name
                        for field in reading.fields
                        if field.name == term["operand"]
                        or field.name in (term["filter"] or {})
                    }
                )
                wanted.add((reading.entity, reading.input_attr))
                continue
            if term["operand"] != "entity":
                wanted.add((entity, term["operand"]))
            for attr in term["filter"] or {}:
                wanted.add((entity, str(attr)))
        if parsed["window"]:
            wanted.add((spec.get("entity"), parsed["window"]["attr"]))
        if parsed["group_by"]:
            path = PATH_RE.match(parsed["group_by"])
            if path:
                wanted.add((path.group(1), path.group(2)))
            else:
                wanted.add((spec.get("entity"), parsed["group_by"]))
        mapped: set = set()
        for pair in wanted:
            mapped |= _mapped_pairs(specs, *pair)
        fields = sorted(
            {
                f"{line.source}.{line.object_type}.{'.'.join(line.path)}"
                for key in mapped
                for line in by_entity_label.get(key, [])
            }
        )
        out[name] = {
            "label": spec.get("label", name),
            "raw_fields": fields,
            "attrs": sorted(f"{e}.{a}" for e, a in wanted),
        }
        if inferred_from is not None:
            out[name]["inferred"] = True
            out[name]["inferred_from"] = inferred_from
    return out
