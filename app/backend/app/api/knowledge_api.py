from app.api.routers import knowledge as router
from app.engine import mappings, metrics, ontology, transforms
from app.sources import hooks


@router.get("/ontology")
async def get_ontology():
    onto = ontology.load()
    return {
        "source_priority": list(onto.source_priority),
        "entities": {
            name: {"identity": list(spec.identity), "attrs": spec.attrs}
            for name, spec in sorted(onto.entities.items())
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
