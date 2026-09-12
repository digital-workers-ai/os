from app.api.insights_api import rule_definitions
from app.api.routers import definitions as router
from app.engine import (
    dashboards,
    derived,
    goals,
    mappings,
    metrics,
    ontology,
    transforms,
)
from app.sources import hooks


def _gloss(glossary, attr) -> dict:
    gloss = glossary.get(attr) or ontology.AttributeGloss()
    return {"description": gloss.description, "synonyms": list(gloss.synonyms)}


@router.get("/ontology")
async def get_ontology():
    onto = ontology.load()
    return {
        "source_priority": list(onto.source_priority),
        "entities": {
            name: {
                "identity": list(spec.identity),
                "attrs": spec.attrs,
                "description": spec.description,
                "synonyms": list(spec.synonyms),
            }
            for name, spec in sorted(onto.entities.items())
        },
        "attributes": {
            label: {
                "description": gloss.description,
                "synonyms": list(gloss.synonyms),
            }
            for label, gloss in sorted(onto.attributes.items())
        },
        "relationships": [
            {
                "rel": rel.rel,
                "from": rel.from_type,
                "to": rel.to_type,
                "cardinality": rel.cardinality,
                "grounding": rel.grounding,
            }
            for rel in onto.relationships
        ],
    }


@router.get("/derived")
async def get_derived():
    specs = derived.load()
    glossary = ontology.load().attributes
    types = {entity: derived.types_for(entity) for entity in specs}
    return {
        "derived": {
            entity: {
                attr: {
                    "expression": str(spec.get("expression")),
                    "via": str(spec.get("via")),
                    "filter": spec.get("filter") or {},
                    **_gloss(glossary, attr),
                    "type": types[entity].get(attr),
                }
                for attr, spec in attrs.items()
            }
            for entity, attrs in specs.items()
        }
    }


@router.get("/mappings")
async def get_mappings():
    transform_map = transforms.load_map()
    return {
        "lines": [
            {
                "entity": line.entity,
                "source": line.source,
                "object_type": line.object_type,
                "path": ".".join(line.path),
                "label": line.label,
                "transform": transform_map.get(line.label),
                "from_hook": line.path[0].startswith("_"),
            }
            for line in mappings.load()
        ],
        "hook_sources": sorted(hooks.hooks()),
    }


@router.get("/transforms")
async def get_transforms():
    return {
        "labels": transforms.load_map(),
        "registry": {
            name: {"produces": transforms.TRANSFORM_TYPES[name]}
            for name in sorted(transforms.TRANSFORMS)
        },
    }


@router.get("/metrics")
async def get_metric_definitions():
    definitions = metrics.load_definitions()
    return {
        "definitions": definitions,
        "provenance": metrics.provenance(definitions, mappings.load()),
    }


@router.get("/rules")
async def get_rules():
    return await rule_definitions()


@router.get("/goals")
async def get_goals():
    return {
        "goals": {
            name: {
                "metric": spec.get("metric"),
                "target": spec.get("target"),
                "strategy": spec.get("strategy"),
                "params": spec.get("params") or {},
            }
            for name, spec in sorted(goals.definitions().items())
        }
    }


def _card(card, metric_defs, attrs_of) -> dict:
    if isinstance(card, dashboards.TableCard):
        attrs = attrs_of(card.entity)
        return {
            "shape": "table",
            "label": card.label,
            "entity": card.entity,
            "rank": card.rank,
            "columns": [{"attr": attr, "type": attrs[attr]} for attr in card.columns],
            "window_attr": card.window_attr,
            "limit": card.limit,
            "filter": card.filter,
        }
    spec = metric_defs[card]
    return {
        "metric": card,
        "label": spec.get("label", card),
        "shape": dashboards.shape(metrics.parse_spec(spec)),
    }


@router.get("/dashboards")
async def get_dashboards():
    metric_defs = metrics.load_definitions()
    attrs_of = derived.attrs_of(ontology.load())
    return {
        "dashboards": {
            page.name: {
                "label": page.label,
                "range": page.range,
                "goals": page.goals,
                "findings": page.findings,
                "filter": page.filter,
                "sections": [
                    {
                        "label": section.label,
                        "cards": [
                            _card(card, metric_defs, attrs_of) for card in section.cards
                        ],
                    }
                    for section in page.sections
                ],
            }
            for page in dashboards.pages(dashboards.definitions())
        }
    }
