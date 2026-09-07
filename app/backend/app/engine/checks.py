import yaml

from app.caches import BACKEND_DIR
from app.engine import (
    candidates,
    goals,
    mappings,
    metrics,
    ontology,
    rules,
    strategies,
)
from app.engine.transforms import (
    TRANSFORM_TYPES,
    TRANSFORMS,
    TransformError,
    load_map,
)
from app.enrichment import vocabulary
from app.sources import hooks, registry

REAL_FIXTURES = BACKEND_DIR / "fixtures" / "real"

ACCOUNT_LEVEL_ATTR = "currency"


class BuildCheckError(RuntimeError):
    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("build checks failed:\n  - " + "\n  - ".join(problems))


def source_status(lines=None) -> dict:
    if lines is None:
        lines = mappings.load()
    replayed = (
        {d.name for d in REAL_FIXTURES.iterdir() if d.is_dir()}
        if REAL_FIXTURES.is_dir()
        else set()
    )
    entities_by_source: dict = {}
    for line in lines:
        entities_by_source.setdefault(line.source, set()).add(line.entity)
    status = {}
    for source in sorted(registry.discover()):
        entities = entities_by_source.get(source, set())
        if source in replayed:
            label = "provider-validated"
        elif entities:
            label = "mock-validated"
        else:
            label = "unmapped"
        status[source] = {"status": label, "entities": sorted(entities)}
    return status


def _labels_by_entity(lines) -> dict:
    index: dict = {}
    for line in lines:
        index.setdefault(line.entity, {}).setdefault(line.label, []).append(line)
    return index


def run(
    mapping_paths=None,
    ontology_path=None,
    transforms_path=None,
    metrics_path=None,
    rules_path=None,
    goals_path=None,
    enrichment_paths=None,
) -> list[str]:
    problems: list[str] = []

    try:
        lines = [
            line for path in (mapping_paths or [None]) for line in mappings.load(path)
        ]
    except mappings.MappingError as e:
        return [str(e)]
    try:
        onto = ontology.load(ontology_path)
    except ontology.OntologyError as e:
        return [str(e)]
    try:
        transform_map = load_map(transforms_path)
    except TransformError as e:
        return [str(e)]
    modules = registry.discover()
    connectors = set(modules)

    for source in sorted({line.source for line in lines}):
        if source not in connectors:
            problems.append(
                f"mappings: source prefix {source!r} matches no connector — "
                "a mapping line for a source nothing pulls is a dead file"
            )

    by_entity = _labels_by_entity(lines)
    for entity, labels in sorted(by_entity.items()):
        spec = onto.entities.get(entity)
        if spec is None:
            problems.append(
                f"mappings: entity {entity!r} is not declared in ontology.yaml"
            )
            continue
        for label in sorted(labels):
            if label not in spec.attrs:
                problems.append(
                    f"mappings: {entity}.{label} is mapped but not declared as "
                    f"an attr of {entity} in ontology.yaml"
                )

    for entity, spec in sorted(onto.entities.items()):
        mapped = by_entity.get(entity, {})
        for attr in sorted(spec.attrs):
            if attr in mapped:
                continue
            if attr == ACCOUNT_LEVEL_ATTR and any(
                getattr(modules.get(source), "ACCOUNT_CURRENCY", None)
                for source in {
                    line.source for label in mapped.values() for line in label
                }
            ):
                continue
            problems.append(
                f"ontology: {entity}.{attr} is declared but no mapping line "
                "produces it — an attr nothing fills is a promise the data "
                "cannot keep"
            )

    label_types: dict = {}
    for entity, spec in sorted(onto.entities.items()):
        for attr, kind in sorted(spec.attrs.items()):
            prior = label_types.get(attr)
            if prior and prior[1] != kind:
                problems.append(
                    f"label {attr!r} is {kind} on {entity} but {prior[1]} on "
                    f"{prior[0]} — same label must mean the same thing "
                    "everywhere, or the vocabulary has forked"
                )
            label_types.setdefault(attr, (entity, kind))

    for label, fn in sorted(transform_map.items()):
        if fn not in TRANSFORMS:
            problems.append(
                f"transforms: {label!r} names {fn!r}, which is not in the "
                f"registry — available: {sorted(TRANSFORMS)}"
            )
            continue
        if label not in label_types:
            problems.append(
                f"transforms: {label!r} is normalized but is not a declared "
                "ontology attr — an orphan transform entry never runs"
            )
            continue
        declared = label_types[label][1]
        guaranteed = TRANSFORM_TYPES[fn]
        if declared != guaranteed:
            problems.append(
                f"transforms: {label!r} uses {fn} (produces {guaranteed}) but "
                f"ontology declares it {declared}"
            )

    for rel in onto.relationships:
        for side, entity in (("from", rel.from_type), ("to", rel.to_type)):
            if entity not in onto.entities:
                problems.append(
                    f"relationship {rel.rel!r}: {side} {entity!r} is not a "
                    "declared entity"
                )
        if rel.via and onto.attr_type(rel.from_type, rel.via) is None:
            problems.append(
                f"relationship {rel.rel!r}: via {rel.via!r} is not an attr "
                f"of {rel.from_type}"
            )
        if rel.match:
            for entity in (rel.from_type, rel.to_type):
                spec = onto.entities.get(entity)
                if spec and rel.match not in spec.attrs:
                    problems.append(
                        f"relationship {rel.rel!r}: match {rel.match!r} is not "
                        f"an attr of {entity} — a match edge joins one label on "
                        "both sides"
                    )

    for entity, spec in sorted(onto.entities.items()):
        for attr in spec.identity:
            if attr not in transform_map:
                problems.append(
                    f"identity: {entity}.{attr} has no transform — merge "
                    "evidence must be normalized, or exact match compares "
                    "raw provider formatting and merges nothing"
                )

    for entity, spec in sorted(onto.entities.items()):
        review = spec.candidates
        if review is None:
            continue
        for attr in (review.name, *review.corroborate):
            if attr in spec.attrs or candidates.VIRTUAL.get(attr) in spec.attrs:
                continue
            problems.append(
                f"candidates: {entity}.{attr} is named as review evidence but "
                f"{entity} declares no such attr — a nomination on a value no "
                "record carries can never fire"
            )

    money = {label for label, fn in transform_map.items() if fn == "normalize_money"}
    for entity, spec in sorted(onto.entities.items()):
        carried = sorted(set(spec.attrs) & money)
        if carried and "currency" not in spec.attrs:
            problems.append(
                f"currency: {entity} carries money ({', '.join(carried)}) but "
                "declares no `currency` attr — the mixed-currency guard has "
                "nothing to compare, so it would pass silently"
            )
    for entity, labels in sorted(by_entity.items()):
        for label in sorted(set(labels) & money):
            for line in labels[label]:
                declares = bool(
                    getattr(modules.get(line.source), "ACCOUNT_CURRENCY", None)
                )
                maps_currency = any(
                    ln.source == line.source for ln in labels.get("currency", [])
                )
                if not (declares or maps_currency):
                    problems.append(
                        f"currency: {line.source} maps {entity}.{label} but "
                        "neither maps `currency` nor declares ACCOUNT_CURRENCY "
                        "— money would be stored with no way to know what it is "
                        "denominated in"
                    )

    hook_sources = set(hooks.hooks())
    hook_fields = {line for line in lines if line.path[0].startswith("_")}
    for line in sorted(hook_fields, key=lambda ln: ln.key):
        if line.source not in hook_sources:
            problems.append(
                f"mappings: {line.key} reads {line.path[0]!r}, which only an "
                f"extract hook can produce, but {line.source!r} has no "
                "extract module"
            )

    try:
        defs = metrics.load_definitions(metrics_path)
    except (metrics.MetricSpecError, yaml.YAMLError) as e:
        problems.append(f"metrics: {e}")
        defs = {}
    for name, spec in sorted((defs or {}).items()):
        try:
            parsed = metrics.parse_spec(spec)
        except metrics.MetricSpecError as e:
            problems.append(f"metric {name!r}: {e}")
            continue
        entity = str(spec.get("entity"))
        spec_entity = onto.entities.get(entity)
        if spec_entity is None:
            problems.append(
                f"metric {name!r}: entity {entity!r} is not declared in the ontology"
            )
            continue
        for term in parsed["terms"]:
            if term["source"] == "enriched":
                continue
            term_entity = str(term.get("entity") or entity)
            term_spec = onto.entities.get(term_entity)
            if term_spec is None:
                problems.append(
                    f"metric {name!r}: term entity {term_entity!r} is not "
                    "declared in the ontology"
                )
                continue
            if term["operand"] != "entity" and term["operand"] not in term_spec.attrs:
                problems.append(
                    f"metric {name!r}: aggregates {term['operand']!r}, which is "
                    f"not an attr of {term_entity}"
                )
            if (
                term["agg"] in ("SUM", "AVG")
                and term["operand"] != "entity"
                and term_spec.attrs.get(term["operand"]) != "number"
            ):
                problems.append(
                    f"metric {name!r}: {term['agg']}({term['operand']}) over a "
                    f"{term_spec.attrs.get(term['operand'])} attr — "
                    "arithmetic on a non-number is a category error"
                )
            for attr in term["filter"] or {}:
                if str(attr) not in term_spec.attrs:
                    problems.append(
                        f"metric {name!r}: filters on {attr!r}, which is not an "
                        f"attr of {term_entity}"
                    )

    lineage = metrics.provenance(defs or {}, lines)
    for name in sorted(defs or {}):
        if name in lineage and not lineage[name]["raw_fields"]:
            reparsed = metrics.parse_spec(defs[name])
            counts_only = all(
                term["operand"] == "entity" and not (term["filter"] or {})
                for term in reparsed["terms"]
            )
            if not counts_only and not reparsed["inferred"]:
                problems.append(
                    f"metric {name!r}: no raw field feeds it — provenance would "
                    "be empty, so the number could not show its receipts"
                )

    problems += check_enrichment(onto, enrichment_paths)

    try:
        problems += check_rules(onto, rules.load(rules_path))
    except (rules.RuleError, yaml.YAMLError) as e:
        problems.append(f"rules.yaml: {e}")
    try:
        problems += check_goals(goals.load(goals_path), defs)
    except (goals.GoalError, yaml.YAMLError) as e:
        problems.append(f"goals.yaml: {e}")

    return problems


def check_rules(onto, definitions) -> list[str]:
    problems: list[str] = []
    for name, body in sorted((definitions or {}).items()):
        if isinstance(body, rules.Rule):
            rule = body
        else:
            try:
                rule = rules.parse(str(name), body)
            except rules.RuleError as e:
                problems.append(f"rule {name!r}: {e}")
                continue

        spec = onto.entities.get(rule.entity)
        if spec is None:
            problems.append(
                f"rule {name!r}: entity {rule.entity!r} is not declared in "
                "ontology.yaml"
            )
            continue
        if not rule.conditions:
            problems.append(
                f"rule {name!r} has no conditions — a predicate true of every "
                "entity is not a signal, it is a list of the estate"
            )

        for condition in rule.conditions:
            if condition.op not in rules.OPERATORS:
                problems.append(
                    f"rule {name!r}: unknown operator {condition.op!r} on "
                    f"{condition.attr!r} — known: {sorted(rules.OPERATORS)}"
                )
                continue
            kind = spec.attrs.get(condition.attr)
            if kind is None:
                problems.append(
                    f"rule {name!r}: {rule.entity}.{condition.attr} is not a "
                    f"declared attr of {rule.entity}"
                )
                continue
            if condition.op in rules.DATE_OPS and kind != "date":
                problems.append(
                    f"rule {name!r}: {condition.op} on "
                    f"{rule.entity}.{condition.attr}, which is {kind!r} and "
                    "not a date — the operator compares against the clock"
                )
            if condition.op in rules.NUMERIC_OPS and kind != "number":
                problems.append(
                    f"rule {name!r}: {condition.op} on "
                    f"{rule.entity}.{condition.attr}, which is {kind!r} — "
                    "arithmetic on a non-number is a category error"
                )
            if condition.op in (rules.NUMERIC_OPS | rules.DATE_OPS):
                try:
                    float(condition.operand)
                except (TypeError, ValueError):
                    problems.append(
                        f"rule {name!r}: threshold {condition.operand!r} on "
                        f"{condition.attr!r} is not numeric"
                    )
    return problems


def check_goals(definitions, metric_defs=None) -> list[str]:
    problems: list[str] = []
    known_metrics = set(
        metric_defs if metric_defs is not None else metrics.load_definitions()
    )
    for name, spec in sorted((definitions or {}).items()):
        if not isinstance(spec, dict):
            problems.append(f"goal {name!r} must be a mapping")
            continue
        missing = [k for k in goals.REQUIRED if spec.get(k) is None]
        if missing:
            problems.append(f"goal {name!r} is missing {missing}")
            continue

        metric = str(spec["metric"])
        if metric not in known_metrics:
            problems.append(
                f"goal {name!r}: metric {metric!r} is not defined in "
                "metrics.yaml — a goal on a renamed metric reports unknown "
                "forever with nothing to notice"
            )
        strategy = str(spec["strategy"])
        if strategy not in strategies.STRATEGIES:
            problems.append(
                f"goal {name!r}: strategy {strategy!r} is not registered — "
                f"known: {sorted(strategies.STRATEGIES)}"
            )
        else:
            allowed = set(strategies.PARAMS[strategy])
            unknown = set(spec.get("params") or {}) - allowed
            if unknown:
                problems.append(
                    f"goal {name!r}: {sorted(unknown)} "
                    f"{'is' if len(unknown) == 1 else 'are'} not a parameter of "
                    f"{strategy} — it would be silently ignored, which is how a "
                    f"tuned goal stays untuned. Accepted: {sorted(allowed)}"
                )
            for param, value in sorted((spec.get("params") or {}).items()):
                if param not in allowed:
                    continue
                try:
                    float(value)
                except (TypeError, ValueError):
                    problems.append(
                        f"goal {name!r}: parameter {param}={value!r} is not "
                        f"numeric — {strategy} reads it as a number and would "
                        "raise on the first request rather than at build time"
                    )
        try:
            float(spec["target"])
        except (TypeError, ValueError):
            problems.append(f"goal {name!r}: target {spec['target']!r} is not numeric")
    return problems


def check_enrichment(onto, enrichment_paths=None) -> list[str]:
    problems: list[str] = []
    try:
        readings = vocabulary.load(enrichment_paths)
    except vocabulary.VocabularyError as e:
        return [str(e)]

    for name, reading in sorted(readings.items()):
        spec = onto.entities.get(reading.entity)
        if spec is None:
            problems.append(
                f"enrichment.yaml: reading {name!r} reads entity "
                f"{reading.entity!r}, which ontology.yaml does not declare"
            )
            continue
        if reading.input_attr not in spec.attrs:
            problems.append(
                f"enrichment.yaml: reading {name!r} reads "
                f"{reading.entity}.{reading.input_attr}, which is not an attr "
                f"of {reading.entity} in ontology.yaml"
            )
            continue
        declared = spec.attrs[reading.input_attr]
        if declared != "string":
            problems.append(
                f"enrichment.yaml: reading {name!r} reads "
                f"{reading.entity}.{reading.input_attr}, declared as "
                f"{declared!r} — the layer reads free text, and a number or a "
                "date has nothing in it to read"
            )
        if reading.input_attr in (spec.identity or ()):
            problems.append(
                f"enrichment.yaml: reading {name!r} reads "
                f"{reading.entity}.{reading.input_attr}, which is a merge "
                "identity attr — feeding an identifier to a model is never "
                "what was meant"
            )
    return problems
