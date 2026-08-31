import re

from sqlalchemy import func, select

from app.caches import BACKEND_DIR, load_mapping
from app.engine import transforms
from app.models import EntityCanonical, FactCurrent

DEFAULT_METRICS = BACKEND_DIR / "metrics.yaml"

_AGG_RE = re.compile(r"^(SUM|AVG|COUNT)\((\w+)\)$")
_ATTR_RE = re.compile(r"^\w+$")

ID_CHUNK = 8000


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


def parse_spec(spec) -> dict:
    if not isinstance(spec, dict):
        raise MetricSpecError("metric spec must be a mapping")
    match = _AGG_RE.match(str(spec.get("expression") or ""))
    if not match:
        raise MetricSpecError(f"bad expression: {spec.get('expression')!r}")
    if not spec.get("entity"):
        raise MetricSpecError("metric is missing `entity`")
    filt = spec.get("filter")
    if filt is not None:
        if not isinstance(filt, dict):
            raise MetricSpecError("filter must be a mapping of attr → value")
        for attr in filt:
            if not _ATTR_RE.match(str(attr)):
                raise MetricSpecError(
                    f"filter attr {attr!r} is not a plain attribute name"
                )
    return {
        "terms": [{"agg": match.group(1), "operand": match.group(2), "filter": filt}]
    }


async def _in_chunks(session, ids, build) -> list:
    ordered = list(ids)
    rows: list = []
    for start in range(0, len(ordered), ID_CHUNK):
        rows.extend(
            (await session.execute(build(ordered[start : start + ID_CHUNK]))).all()
        )
    return rows


async def _ids_for(session, entity_type: str, filt) -> tuple:
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


async def _measure(session, spec: dict, terms: list, money: set) -> dict:
    term = terms[0]
    ids, notes = await _ids_for(session, spec["entity"], term["filter"])
    value, agg_notes = await _aggregate(
        session, ids, term["agg"], term["operand"], money
    )
    result = {"value": value, "entities": len(ids), **notes, **agg_notes}
    if not ids:
        result["note"] = (
            "no entities matched — no data, as opposed to a zero measurement"
        )
    return result


async def evaluate_definitions(session, defs: dict) -> dict:
    money = money_labels()
    out: dict = {}
    for name, spec in defs.items():
        label = spec.get("label", name) if isinstance(spec, dict) else name
        try:
            parsed = parse_spec(spec)
            result = await _measure(session, spec, parsed["terms"], money)
            result["label"] = label
            result["entity"] = spec.get("entity")
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


async def evaluate(session) -> dict:
    return await evaluate_definitions(session, load_definitions())


def provenance(defs: dict, lines) -> dict:
    by_entity_label: dict = {}
    for line in lines:
        by_entity_label.setdefault((line.entity, line.label), []).append(line)

    out: dict = {}
    for name, spec in defs.items():
        try:
            parsed = parse_spec(spec)
        except MetricSpecError:
            continue
        entity = spec.get("entity")
        term = parsed["terms"][0]
        wanted: set = set()
        if term["operand"] != "entity":
            wanted.add((entity, term["operand"]))
        for attr in term["filter"] or {}:
            wanted.add((entity, str(attr)))
        fields = sorted(
            {
                f"{line.source}.{line.object_type}.{'.'.join(line.path)}"
                for key in wanted
                for line in by_entity_label.get(key, [])
            }
        )
        out[name] = {
            "label": spec.get("label", name),
            "raw_fields": fields,
            "attrs": sorted(f"{e}.{a}" for e, a in wanted),
        }
    return out
