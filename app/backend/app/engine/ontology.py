from dataclasses import dataclass
from pathlib import Path

from app.caches import KNOWLEDGE_DIR, load_mapping

DEFAULT_ONTOLOGY = KNOWLEDGE_DIR / "ontology.yaml"

TYPES = ("string", "number", "date")


class OntologyError(ValueError):
    pass


@dataclass(frozen=True)
class EntitySpec:
    name: str
    attrs: dict


@dataclass(frozen=True)
class Ontology:
    entities: dict

    def attr_type(self, entity: str, attr: str) -> str | None:
        spec = self.entities.get(entity)
        return spec.attrs.get(attr) if spec else None


def load(path=None) -> Ontology:
    path = Path(path or DEFAULT_ONTOLOGY)
    doc = load_mapping(path, OntologyError)

    raw_entities = doc.get("entities")
    if not isinstance(raw_entities, dict) or not raw_entities:
        raise OntologyError(f"{path.name}: `entities:` must be a non-empty mapping")

    entities: dict[str, EntitySpec] = {}
    for name, spec in raw_entities.items():
        if not isinstance(spec, dict):
            raise OntologyError(f"entity {name!r} must be a mapping")
        attrs = spec.get("attrs")
        if not isinstance(attrs, dict) or not attrs:
            raise OntologyError(f"entity {name!r} declares no attrs")
        for attr, kind in attrs.items():
            if kind not in TYPES:
                raise OntologyError(
                    f"{name}.{attr}: type {kind!r} is not one of {list(TYPES)}"
                )
        entities[str(name)] = EntitySpec(name=str(name), attrs=dict(attrs))

    return Ontology(entities=entities)
