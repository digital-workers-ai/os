import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, create_model

from app import caches
from app.caches import KNOWLEDGE_DIR, load_mapping

DEFAULT_ENRICHMENT_FILES = [KNOWLEDGE_DIR / "enrichment.yaml"]

KINDS = ("one_of", "many_of")
_SNAKE = re.compile(r"^[a-z][a-z0-9_]*$")


class VocabularyError(ValueError):
    pass


@dataclass(frozen=True)
class Field:
    name: str
    kind: str
    labels: tuple
    description: str
    glosses: tuple

    def meaning(self, label: str) -> str:
        return dict(self.glosses).get(label, "")


@dataclass(frozen=True)
class Reading:
    name: str
    entity: str
    input_attr: str
    description: str
    fields: tuple
    origin: str
    sha: str


def _spec_digest(payload: dict) -> str:
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _parse_labels(origin: str, reading: str, field: str, raw) -> tuple:
    if isinstance(raw, dict):
        pairs = [(str(k), str(v or "").strip()) for k, v in raw.items()]
    elif isinstance(raw, list):
        pairs = [(str(item), "") for item in raw]
    else:
        raise VocabularyError(
            f"{origin}: {reading}.{field} labels must be a list or a "
            f"label: meaning mapping, got {type(raw).__name__}"
        )
    if not pairs:
        raise VocabularyError(
            f"{origin}: {reading}.{field} has no labels — a question with no "
            "possible answer generates an empty enum, which the API rejects "
            "with a message about JSON Schema rather than about this file"
        )
    seen = set()
    for label, _meaning in pairs:
        if label in seen:
            raise VocabularyError(
                f"{origin}: {reading}.{field} has duplicate label {label!r}"
            )
        seen.add(label)
        if not _SNAKE.match(label):
            raise VocabularyError(
                f"{origin}: {reading}.{field} label {label!r} is not snake_case. "
                "Labels are stored, compared and grouped — 'Strong' and "
                "'strong' looking like one value in a report and two in a "
                "GROUP BY is discovered a quarter later"
            )
    return tuple(pairs)


def _parse_reading(origin: str, name: str, body) -> Reading:
    if not isinstance(body, dict):
        raise VocabularyError(f"{origin}: reading {name!r} must be a mapping")
    if not _SNAKE.match(name):
        raise VocabularyError(f"{origin}: reading name {name!r} is not snake_case")
    entity = str(body.get("entity") or "").strip()
    input_attr = str(body.get("input") or "").strip()
    if not entity:
        raise VocabularyError(f"{origin}: reading {name!r} names no entity")
    if not input_attr:
        raise VocabularyError(
            f"{origin}: reading {name!r} names no input attr — the layer needs "
            "to know which ontology attr holds the text it reads"
        )
    raw_fields = body.get("fields")
    if not isinstance(raw_fields, dict) or not raw_fields:
        raise VocabularyError(
            f"{origin}: reading {name!r} has no fields — a reading that asks "
            "nothing writes nothing"
        )

    fields = []
    for field_name, spec in raw_fields.items():
        field_name = str(field_name)
        if not _SNAKE.match(field_name):
            raise VocabularyError(f"{origin}: {name}.{field_name} is not snake_case")
        if not isinstance(spec, dict):
            raise VocabularyError(f"{origin}: {name}.{field_name} must be a mapping")
        kind = str(spec.get("type") or "").strip()
        if kind not in KINDS:
            raise VocabularyError(
                f"{origin}: {name}.{field_name} type {kind!r} is not one of "
                f"{list(KINDS)}"
            )
        glosses = _parse_labels(origin, name, field_name, spec.get("labels"))
        fields.append(
            Field(
                name=field_name,
                kind=kind,
                labels=tuple(label for label, _ in glosses),
                description=str(spec.get("description") or "").strip(),
                glosses=glosses,
            )
        )

    digest = _spec_digest(
        {
            "entity": entity,
            "input": input_attr,
            "description": str(body.get("description") or "").strip(),
            "fields": [
                [f.name, f.kind, f.description, [list(g) for g in f.glosses]]
                for f in fields
            ],
        }
    )

    return Reading(
        name=name,
        entity=entity,
        input_attr=input_attr,
        description=str(body.get("description") or "").strip(),
        fields=tuple(fields),
        origin=origin,
        sha=digest,
    )


_cache: dict | None = None
_models: dict = {}


def _reset() -> None:
    global _cache
    _cache = None
    _models.clear()


def load(paths=None) -> dict:
    global _cache
    if paths is None and _cache is not None:
        return _cache
    files = [Path(p) for p in (paths or DEFAULT_ENRICHMENT_FILES)]
    readings: dict = {}
    for path in files:
        doc = load_mapping(path, VocabularyError)
        entries = doc.get("readings")
        if entries is None:
            raise VocabularyError(f"{path.name}: no `readings:` block")
        if not isinstance(entries, dict):
            raise VocabularyError(f"{path.name}: `readings:` must be a mapping")
        for name, body in entries.items():
            readings[str(name)] = _parse_reading(path.name, str(name), body)
    if paths is None:
        _cache = readings
    return readings


def _camel(text: str) -> str:
    return "".join(part.title() for part in text.split("_") if part)


def model_for(reading: Reading) -> type[BaseModel]:
    key = (reading.name, reading.sha)
    if key in _models:
        return _models[key]

    strict = ConfigDict(extra="forbid")
    attrs: dict = {}
    for field in reading.fields:
        prefix = f"{_camel(reading.name)}{_camel(field.name)}"
        label_enum = Enum(
            f"{prefix}Label", {label: label for label in field.labels}, type=str
        )
        finding = create_model(
            f"{prefix}Finding",
            __config__=strict,
            label=(label_enum, ...),
            quote=(str, ...),
        )
        finding.__doc__ = (
            field.description or f"One {field.name} answer with its evidence."
        )
        attrs[field.name] = (
            (finding, ...) if field.kind == "one_of" else (list[finding], ...)
        )

    model = create_model(f"{_camel(reading.name)}Reading", __config__=strict, **attrs)
    model.__doc__ = reading.description or f"A reading of one {reading.entity}."
    _models[key] = model
    return model


caches.register(_reset)
