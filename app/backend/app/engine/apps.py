import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from app import caches
from app.engine import mappings, ontology
from app.enrichment import vocabulary

APPS_DIR = caches.DEFINITIONS_DIR / "apps"
SCRIPTS_DIR = caches.BACKEND_DIR / "app" / "custom" / "apps"

INPUTS = ("photo", "pdf", "scan", "voice")
KEYS = (
    "title",
    "description",
    "input",
    "roles",
    "lands_as",
    "fields",
    "template",
    "script",
)
FIELD_TYPES = (
    "text",
    "number",
    "money",
    "date",
    "one_of",
    "many_of",
    "lookup",
    "photo",
    "list",
    "screen",
)
FIELD_OPTIONS = (
    "type",
    "description",
    "labels",
    "labels_from",
    "unit",
    "entity",
    "by",
    "from",
    "history",
    "filled_by",
    "fields",
    "lands_as",
    "file",
)

_CHOICES = ("one_of", "many_of")
_KINDS = ("grid", "checklist")
_CHILDREN = {"grid": ("rows", "cells"), "checklist": ("items",)}
_SNAKE = re.compile(r"[a-z][a-z0-9_]*")
_LABEL = re.compile(r"[a-z][a-z0-9_]*|[0-9]+")
_RANGE = re.compile(r"(\d+)-(\d+)")


class AppError(ValueError):
    pass


@dataclass(frozen=True)
class Field:
    name: str
    type: str
    description: str
    labels: tuple
    unit: str | None
    entity: str | None
    by: str | None
    from_scan: bool
    history: bool
    by_script: bool
    fields: tuple
    lands_as: str | None
    file: str | None


@dataclass(frozen=True)
class Template:
    kind: str
    rows: dict | None
    columns: dict | None
    cells: dict | None
    sections: dict | None
    items: dict | None


@dataclass(frozen=True)
class App:
    name: str
    title: str
    description: str
    inputs: tuple
    roles: tuple
    lands_as: str | None
    fields: tuple
    template: Template | None
    script: str | None


def _origin(name) -> str:
    return f"apps/{name}/app.yaml"


def _text(value) -> str:
    return str(value or "").strip()


def _inputs(value) -> tuple:
    given = [value] if isinstance(value, str) else value
    if not isinstance(given, list) or not given:
        raise AppError(
            f"input must be one of {list(INPUTS)} or a non-empty list of them"
        )
    for item in given:
        if item not in INPUTS:
            raise AppError(f"input {item!r} is not one of {list(INPUTS)}")
    return tuple(given)


def _roles(value) -> tuple:
    if not isinstance(value, list) or not value:
        raise AppError("roles must be a non-empty list of snake_case names")
    for role in value:
        if not (isinstance(role, str) and _SNAKE.fullmatch(role)):
            raise AppError(f"role {role!r} is not snake_case")
    return tuple(value)


def _borrowed(path, source) -> tuple:
    reading_name, _dot, field_name = source.partition(".")
    reading = vocabulary.load().get(reading_name)
    if reading is None:
        raise AppError(
            f"{path} labels_from {source!r} names no reading in enrichment.yaml"
        )
    for field in reading.fields:
        if field.name == field_name:
            return field.glosses
    raise AppError(
        f"{path} labels_from {source!r} names no field of reading {reading_name!r}"
    )


def _labels(path, spec) -> tuple:
    borrowed = spec.get("labels_from")
    if borrowed is not None:
        return _borrowed(path, str(borrowed))
    raw = spec.get("labels")
    if isinstance(raw, dict):
        pairs = [(str(label), _text(meaning)) for label, meaning in raw.items()]
    elif isinstance(raw, list):
        pairs = [(str(label), "") for label in raw]
    else:
        raise AppError(
            f"{path} labels must be a list or a label: meaning mapping, got "
            f"{type(raw).__name__}"
        )
    if not pairs:
        raise AppError(
            f"{path} has no labels — a question with no possible answer generates "
            "an empty enum, which the API rejects with a message about JSON Schema "
            "rather than about this file"
        )
    seen = set()
    for label, _meaning in pairs:
        if label in seen:
            raise AppError(f"{path} has duplicate label {label!r}")
        seen.add(label)
        if not _LABEL.fullmatch(label):
            raise AppError(
                f"{path} label {label!r} is not snake_case. Labels are stored, "
                "compared and grouped — 'Strong' and 'strong' looking like one "
                "value in a report and two in a GROUP BY is discovered a quarter "
                "later"
            )
    return tuple(pairs)


def _fields(where, raw, inputs, scripted) -> tuple:
    if not isinstance(raw, dict) or not raw:
        raise AppError(f"{where} must be a non-empty mapping of field name to options")
    return tuple(
        _field(f"{where}.{name}", str(name), spec, inputs, scripted)
        for name, spec in raw.items()
    )


def _field(path, name, spec, inputs, scripted) -> Field:
    if not isinstance(spec, dict):
        raise AppError(f"{path} must be a mapping of options")
    unknown = [key for key in spec if key not in FIELD_OPTIONS]
    if unknown:
        raise AppError(
            f"{path}: unknown option {unknown[0]!r} — known: {list(FIELD_OPTIONS)}"
        )
    kind = spec.get("type")
    if kind not in FIELD_TYPES:
        raise AppError(f"{path} type {kind!r} is not one of {list(FIELD_TYPES)}")
    origin, filler, file = spec.get("from"), spec.get("filled_by"), spec.get("file")
    if origin not in (None, "scan"):
        raise AppError(f"{path} from {origin!r} can only be scan")
    if origin == "scan" and "scan" not in inputs:
        raise AppError(f"{path} from: scan needs scan in input")
    if filler not in (None, "script"):
        raise AppError(f"{path} filled_by {filler!r} can only be script")
    if filler == "script" and not scripted:
        raise AppError(f"{path} filled_by: script needs a script")
    if kind == "screen" and file != "screen.tsx":
        raise AppError(f"{path} file {file!r} must be screen.tsx")
    listed = kind == "list"
    return Field(
        name=name,
        type=kind,
        description=_text(spec.get("description")),
        labels=_labels(path, spec) if kind in _CHOICES else (),
        unit=spec.get("unit"),
        entity=spec.get("entity"),
        by=spec.get("by"),
        from_scan=origin == "scan",
        history=bool(spec.get("history")),
        by_script=filler == "script",
        fields=(
            _fields(f"{path}.fields", spec.get("fields"), inputs, scripted)
            if listed
            else ()
        ),
        lands_as=spec.get("lands_as") if listed else None,
        file=file,
    )


def _part(kind, body, part) -> dict:
    value = body.get(part)
    if not isinstance(value, dict) or not value:
        raise AppError(f"template.{kind}.{part} must be a non-empty mapping")
    return value


def _axis(part, axis) -> str:
    name = axis.get("name")
    if not isinstance(name, str) or not name:
        raise AppError(f"template.grid.{part} needs a name")
    return name


def _values(part, values) -> tuple:
    if isinstance(values, list) and values:
        return tuple(str(value) for value in values)
    bounds = _RANGE.fullmatch(values) if isinstance(values, str) else None
    if bounds and int(bounds[1]) <= int(bounds[2]):
        return tuple(str(n) for n in range(int(bounds[1]), int(bounds[2]) + 1))
    raise AppError(
        f"template.grid.{part} values {values!r} must be a non-empty list or a "
        "range like 1-32"
    )


def _entries(section, entries) -> tuple:
    if not isinstance(entries, list) or not entries:
        raise AppError(
            f"template.checklist.sections.{section} must be a non-empty list of items"
        )
    return tuple(str(entry) for entry in entries)


def _grid(body, inputs, scripted) -> Template:
    rows, columns, cells = (
        _part("grid", body, part) for part in ("rows", "columns", "cells")
    )
    return Template(
        kind="grid",
        rows={
            "name": _axis("rows", rows),
            "values": _values("rows", rows.get("values")),
            "lands_as": rows.get("lands_as"),
            "fields": _fields(
                "template.grid.rows.fields", rows.get("fields"), inputs, scripted
            ),
        },
        columns={
            "name": _axis("columns", columns),
            "values": _values("columns", columns.get("values")),
        },
        cells={
            "lands_as": cells.get("lands_as"),
            "fields": _fields(
                "template.grid.cells.fields", cells.get("fields"), inputs, scripted
            ),
        },
        sections=None,
        items=None,
    )


def _checklist(body, inputs, scripted) -> Template:
    sections = _part("checklist", body, "sections")
    items = _part("checklist", body, "items")
    return Template(
        kind="checklist",
        rows=None,
        columns=None,
        cells=None,
        sections={
            str(name): _entries(str(name), entries)
            for name, entries in sections.items()
        },
        items={
            "lands_as": items.get("lands_as"),
            "fields": _fields(
                "template.checklist.items.fields", items.get("fields"), inputs, scripted
            ),
        },
    )


_BUILDERS = {"grid": _grid, "checklist": _checklist}


def _template(raw, inputs, scripted) -> Template | None:
    if raw is None:
        return None
    kinds = list(raw) if isinstance(raw, dict) else []
    if len(kinds) != 1 or kinds[0] not in _KINDS:
        raise AppError(f"template must be exactly one of {list(_KINDS)}")
    body = raw[kinds[0]] if isinstance(raw[kinds[0]], dict) else {}
    return _BUILDERS[kinds[0]](body, inputs, scripted)


def _app(name, raw) -> App:
    if not _SNAKE.fullmatch(name):
        raise AppError(f"app name {name!r} is not snake_case")
    if not isinstance(raw, dict):
        raise AppError("top level must be a mapping")
    unknown = [key for key in raw if key not in KEYS]
    if unknown:
        raise AppError(f"unknown key {unknown[0]!r} — known: {list(KEYS)}")
    title = raw.get("title")
    if not isinstance(title, str) or not title.strip():
        raise AppError("title must be non-empty text")
    inputs = _inputs(raw.get("input"))
    roles = _roles(raw.get("roles"))
    script = raw.get("script")
    if script not in (None, "script.py"):
        raise AppError(f"script {script!r} must be script.py")
    scripted = script is not None
    return App(
        name=name,
        title=title.strip(),
        description=_text(raw.get("description")),
        inputs=inputs,
        roles=roles,
        lands_as=raw.get("lands_as"),
        fields=_fields("fields", raw.get("fields"), inputs, scripted),
        template=_template(raw.get("template"), inputs, scripted),
        script=script,
    )


def parse(name, raw) -> App:
    try:
        return _app(str(name), raw)
    except AppError as e:
        raise AppError(f"{_origin(name)}: {e}") from None


def _read(folder) -> App:
    path = folder / "app.yaml"
    if not path.is_file():
        raise AppError(f"{_origin(folder.name)}: the folder has no app.yaml")
    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        raise AppError(f"{_origin(folder.name)}: does not parse — {e}") from None
    return parse(folder.name, raw)


def _folders(root) -> list[Path]:
    return sorted(entry for entry in Path(root).iterdir() if entry.is_dir())


def names() -> list[str]:
    return [folder.name for folder in _folders(APPS_DIR)]


def _load_all() -> dict:
    return {folder.name: _read(folder) for folder in _folders(APPS_DIR)}


apps = caches.cached(_load_all)


def load(name) -> App:
    loaded = apps()
    if name not in loaded:
        raise AppError(f"no app named {name!r} — known: {list(loaded)}")
    return loaded[name]


def _path(where, name) -> str:
    return f"{where}.fields.{name}" if where else f"fields.{name}"


def _at(where, text) -> str:
    return f"{where} {text}" if where else text


def _lists(app_name, where, fields):
    for field in fields:
        if field.type == "list":
            inner = _path(where, field.name)
            yield (
                inner,
                field.lands_as,
                field.fields,
                f"custom.{app_name}._{field.name}_",
            )
            yield from _lists(app_name, inner, field.fields)


def _containers(app) -> list[tuple]:
    template = app.template
    tops = [("", app.lands_as, app.fields, f"custom.{app.name}.")]
    for part in _CHILDREN[template.kind] if template else ():
        body = getattr(template, part)
        tops.append(
            (
                f"template.{template.kind}.{part}",
                body["lands_as"],
                body["fields"],
                f"custom.{app.name}._{part}_",
            )
        )
    return [
        found
        for where, lands_as, fields, key in tops
        for found in ((where, lands_as, fields, key), *_lists(app.name, where, fields))
    ]


def _lookup(path, field, onto) -> list[str]:
    spec = onto.entities.get(field.entity)
    if spec is None:
        return [f"{path} entity {field.entity!r} is not an entity in ontology.yaml"]
    if field.by is not None and field.by not in spec.attrs:
        return [
            f"{path} by {field.by!r} is not an attr of {field.entity} in ontology.yaml"
        ]
    return []


def _problems(app, onto, mapped) -> list[str]:
    problems: list[str] = []
    for where, lands_as, fields, key in _containers(app):
        if lands_as not in onto.entities:
            problems.append(
                _at(where, f"lands_as {lands_as!r} is not an entity in ontology.yaml")
            )
        for field in fields:
            path = _path(where, field.name)
            if field.type == "lookup":
                problems += _lookup(path, field, onto)
            if field.type != "list" and f"{key}{field.name}" not in mapped:
                problems.append(
                    f"{path} needs a mapping line {key}{field.name} in mappings.yaml"
                )
    if app.script and not (SCRIPTS_DIR / app.name / app.script).is_file():
        problems.append(f"app/custom/apps/{app.name}/{app.script} is missing")
    return problems


def check(path=None) -> list[str]:
    root = Path(path or APPS_DIR)
    if not root.is_dir():
        return [f"apps/: {root} is not a directory"]
    onto = ontology.load()
    mapped = {line.key for line in mappings.load()}
    problems: list[str] = []
    for folder in _folders(root):
        try:
            app = _read(folder)
        except AppError as e:
            problems.append(str(e))
            continue
        problems += [
            f"{_origin(app.name)}: {problem}"
            for problem in _problems(app, onto, mapped)
        ]
    return problems
