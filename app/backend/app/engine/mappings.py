from dataclasses import dataclass
from pathlib import Path

from app.caches import KNOWLEDGE_DIR, load_mapping

DEFAULT_MAPPINGS = KNOWLEDGE_DIR / "mappings.yaml"


class MappingError(ValueError):
    pass


@dataclass(frozen=True)
class MappingLine:
    entity: str
    source: str
    object_type: str
    path: tuple
    label: str
    key: str


def split_key(key: str) -> list[str]:
    segments, current, i = [], [], 0
    while i < len(key):
        char = key[i]
        if char == "\\" and i + 1 < len(key) and key[i + 1] == ".":
            current.append(".")
            i += 2
            continue
        if char == ".":
            segments.append("".join(current))
            current = []
            i += 1
            continue
        current.append(char)
        i += 1
    segments.append("".join(current))
    return segments


def parse_line(entity: str, key: str, label, origin: str) -> MappingLine:
    if not isinstance(label, str) or not label.strip():
        raise MappingError(f"{origin}: {entity}.{key} has no label")
    segments = split_key(str(key))
    if len(segments) < 3:
        raise MappingError(
            f"{origin}: mapping key {key!r} needs at least "
            f"source.object_type.path — got {len(segments)} segment(s)"
        )
    if any(not s for s in segments):
        raise MappingError(f"{origin}: mapping key {key!r} has an empty segment")
    return MappingLine(
        entity=entity,
        source=segments[0],
        object_type=segments[1],
        path=tuple(segments[2:]),
        label=label.strip(),
        key=str(key),
    )


def load(path=None) -> list[MappingLine]:
    path = Path(path or DEFAULT_MAPPINGS)
    doc = load_mapping(path, MappingError)
    lines: list[MappingLine] = []
    for entity, entries in doc.items():
        if not isinstance(entries, dict):
            raise MappingError(
                f"{path.name}: entity {entity!r} must hold key: label lines"
            )
        for key, label in entries.items():
            lines.append(parse_line(str(entity), str(key), label, path.name))
    return lines


def by_object(lines: list[MappingLine]) -> dict:
    index: dict[tuple, list[MappingLine]] = {}
    for line in lines:
        index.setdefault((line.source, line.object_type), []).append(line)
    return index


_MISSING = object()


def extract_path(payload, path: tuple):
    current = payload
    for segment in path:
        if not isinstance(current, dict) or segment not in current:
            return _MISSING
        current = current[segment]
    return current


def is_missing(value) -> bool:
    return value is _MISSING
