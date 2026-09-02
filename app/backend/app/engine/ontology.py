from dataclasses import dataclass
from pathlib import Path

from app.caches import KNOWLEDGE_DIR, load_mapping

DEFAULT_ONTOLOGY = KNOWLEDGE_DIR / "ontology.yaml"

TYPES = ("string", "number", "date")

IDENTITY_SCOPES = ("global", "tenant")

DEFAULT_IDENTITY_SCOPE = "global"

CARDINALITIES = ("many_to_one", "one_to_one", "one_to_many", "many_to_many")


class OntologyError(ValueError):
    pass


@dataclass(frozen=True)
class Relationship:
    rel: str
    from_type: str
    to_type: str
    cardinality: str
    via: str | None = None
    match: str | None = None

    @property
    def grounding(self) -> str:
        return f"via:{self.via}" if self.via else f"match:{self.match}"


@dataclass(frozen=True)
class EntitySpec:
    name: str
    attrs: dict
    identity: tuple = ()
    identity_scope: dict | None = None

    def scope_of(self, attr: str) -> str:
        return (self.identity_scope or {}).get(attr, DEFAULT_IDENTITY_SCOPE)


@dataclass(frozen=True)
class Ontology:
    entities: dict
    relationships: tuple = ()
    source_priority: tuple = ()

    def attr_type(self, entity: str, attr: str) -> str | None:
        spec = self.entities.get(entity)
        return spec.attrs.get(attr) if spec else None

    def identity_attrs(self, entity: str) -> tuple:
        spec = self.entities.get(entity)
        return spec.identity if spec else ()

    def tenant_scoped_attrs(self, entity: str) -> tuple:
        spec = self.entities.get(entity)
        if not spec:
            return ()
        return tuple(a for a in spec.identity if spec.scope_of(a) == "tenant")

    def priority_index(self, source: str) -> int:
        try:
            return self.source_priority.index(source)
        except ValueError:
            return len(self.source_priority)


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
        identity = spec.get("identity") or []
        if not isinstance(identity, list):
            raise OntologyError(f"entity {name!r}: `identity:` must be a list")
        for attr in identity:
            if attr not in attrs:
                raise OntologyError(
                    f"{name}: identity attr {attr!r} is not a declared attr"
                )
        scopes = spec.get("identity_scope") or {}
        if not isinstance(scopes, dict):
            raise OntologyError(
                f"entity {name!r}: `identity_scope:` must be a mapping of "
                "identity attr to scope"
            )
        for attr, scope in scopes.items():
            if attr not in identity:
                raise OntologyError(
                    f"{name}: identity_scope names {attr!r}, which is not in "
                    "`identity:` — a scope on something that is not merge "
                    "evidence has nothing to qualify"
                )
            if scope not in IDENTITY_SCOPES:
                raise OntologyError(
                    f"{name}.{attr}: identity scope {scope!r} is not one of "
                    f"{list(IDENTITY_SCOPES)}"
                )
        entities[str(name)] = EntitySpec(
            name=str(name),
            attrs=dict(attrs),
            identity=tuple(identity),
            identity_scope={str(k): str(v) for k, v in scopes.items()},
        )

    relationships = []
    seen_rels = set()
    for entry in doc.get("relationships") or []:
        if not isinstance(entry, dict):
            raise OntologyError("each relationship must be a mapping")
        missing = [k for k in ("rel", "from", "to", "cardinality") if not entry.get(k)]
        if missing:
            raise OntologyError(f"relationship {entry!r} is missing {missing}")
        if entry["cardinality"] not in CARDINALITIES:
            raise OntologyError(
                f"relationship {entry['rel']!r}: cardinality "
                f"{entry['cardinality']!r} is not one of {list(CARDINALITIES)}"
            )
        via, match = entry.get("via"), entry.get("match")
        if bool(via) == bool(match):
            raise OntologyError(
                f"relationship {entry['rel']!r} needs exactly one grounding — "
                "`via:` or `match:`"
            )
        key = (entry["rel"], entry["from"], entry["to"])
        if key in seen_rels:
            raise OntologyError(f"duplicate relationship {key}")
        seen_rels.add(key)
        relationships.append(
            Relationship(
                rel=str(entry["rel"]),
                from_type=str(entry["from"]),
                to_type=str(entry["to"]),
                cardinality=str(entry["cardinality"]),
                via=str(via) if via else None,
                match=str(match) if match else None,
            )
        )

    priority = doc.get("source_priority") or []
    if not isinstance(priority, list):
        raise OntologyError("`source_priority:` must be a list of source names")

    return Ontology(
        entities=entities,
        relationships=tuple(relationships),
        source_priority=tuple(str(s) for s in priority),
    )
