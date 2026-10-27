import base64
import datetime
import json
from enum import Enum

import pydantic
from pydantic import BaseModel, ConfigDict, create_model

from app import llm, prompts
from app.config import settings

STRICT = ConfigDict(extra="forbid")
UNREAD = ("photo", "screen")
LABELLED = ("one_of", "many_of")
SCALARS = {
    "text": str,
    "lookup": str,
    "number": float,
    "money": float,
    "date": datetime.date,
}


class ReadError(RuntimeError):
    pass


class Place(BaseModel):
    model_config = STRICT

    row: str | None
    column: str | None
    section: str | None
    item: str | None
    list: str | None


class Update(Place):
    field: str
    value: str | float | list[str] | None


class Heard(BaseModel):
    model_config = STRICT

    updates: list[Update]
    cursor: Place | None
    readback: str


PLACES = tuple(Place.model_fields)


def _camel(text: str) -> str:
    return "".join(part.title() for part in text.split("_") if part)


def _enum(name, values):
    return Enum(name, {value: value for value in values}, type=str)


def _answered(fields):
    return [
        field for field in fields if field.type not in UNREAD and not field.by_script
    ]


def _describe(field):
    unit = f"In {field.unit}." if field.unit else ""
    meanings = [f"{label}: {meaning}." for label, meaning in field.labels if meaning]
    parts = (field.description, unit, *meanings)
    return " ".join(part for part in parts if part) or None


def _slot(field):
    return pydantic.Field(description=_describe(field))


def _kind(field, name):
    if field.type == "list":
        return list[_row(f"{name}Row", field.fields)]
    if field.type in LABELLED:
        labels = _enum(f"{name}Label", [label for label, _ in field.labels])
        return labels if field.type == "one_of" else list[labels]
    return SCALARS[field.type]


def _row(name, fields, **keys):
    values = {
        field.name: (_kind(field, f"{name}{_camel(field.name)}") | None, _slot(field))
        for field in _answered(fields)
    }
    return create_model(name, __config__=STRICT, **keys, **values)


def _answer(field, name):
    return create_model(
        f"{name}Answer",
        __config__=STRICT,
        value=(_kind(field, name) | None, _slot(field)),
        found=(bool, ...),
    )


def _grid(template, prefix):
    row = (_enum(f"{prefix}RowValue", template.rows["values"]), ...)
    column = (_enum(f"{prefix}ColumnValue", template.columns["values"]), ...)
    rows = _row(f"{prefix}TemplateRow", template.rows["fields"], row=row)
    cells = _row(
        f"{prefix}TemplateCell", template.cells["fields"], row=row, column=column
    )
    return create_model(
        f"{prefix}Template",
        __config__=STRICT,
        rows=(list[rows], ...),
        cells=(list[cells], ...),
    )


def _checklist(template, prefix):
    sections = template.sections
    every_item = dict.fromkeys(item for items in sections.values() for item in items)
    items = _row(
        f"{prefix}TemplateItem",
        template.items["fields"],
        section=(_enum(f"{prefix}SectionValue", sections), ...),
        item=(_enum(f"{prefix}ItemValue", every_item), ...),
    )
    return create_model(
        f"{prefix}Template", __config__=STRICT, items=(list[items], ...)
    )


def answer_model(app) -> type[BaseModel]:
    prefix = _camel(app.name)
    attrs = {
        field.name: (_answer(field, f"{prefix}{_camel(field.name)}"), ...)
        for field in _answered(app.fields)
    }
    if app.template is not None:
        shape = _grid if app.template.kind == "grid" else _checklist
        attrs["template"] = (shape(app.template, prefix), ...)
    return create_model(f"{prefix}Answer", __config__=STRICT, **attrs)


def _system(key, app) -> str:
    return (
        f"{prompts.text('custom_reader', key)}\n\n"
        f"The app is {app.title}: {app.description}"
    )


def _block(media_type, data) -> dict:
    return {
        "type": "document" if media_type == "application/pdf" else "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": base64.b64encode(data).decode(),
        },
    }


def _keyed(entries, keys) -> dict:
    return {
        ":".join(entry[key] for key in keys): {
            name: value for name, value in entry.items() if name not in keys
        }
        for entry in entries
    }


def _template(template, answer) -> dict:
    items = [
        item
        for item in answer.get("items", [])
        if item["item"] in template.sections[item["section"]]
    ]
    return {
        "rows": _keyed(answer.get("rows", []), ("row",)),
        "cells": _keyed(answer.get("cells", []), ("row", "column")),
        "items": _keyed(items, ("section", "item")),
    }


def _placed(place) -> dict:
    return {key: place[key] for key in PLACES if place[key] is not None}


def _said(text) -> str:
    if not settings.CUSTOM_ENABLED:
        raise ReadError("reading is off: set CUSTOM_ENABLED")
    return (text or "").strip()


async def _parse(system, user, output_format, client_override) -> dict:
    try:
        parsed, _served_by = await llm.parse(
            model=settings.CUSTOM_MODEL,
            max_tokens=settings.CUSTOM_MAX_TOKENS,
            system=system,
            user=user,
            output_format=output_format,
            fallback=True,
            client_override=client_override,
        )
    except llm.LLMError as exc:
        raise ReadError(str(exc)) from exc
    return parsed.model_dump(mode="json")


async def read(app, *, files, text, client_override=None) -> dict:
    said = _said(text)
    if not files and not said:
        raise ReadError("nothing to read")
    user = [_block(media_type, data) for media_type, data in files]
    user.append(
        {"type": "text", "text": f"What was said or typed: {said or 'nothing'}"}
    )
    answer = await _parse(
        _system("read", app), user, answer_model(app), client_override
    )
    answered = [(field.name, answer[field.name]) for field in _answered(app.fields)]
    result = {
        "fields": {
            name: got["value"] if got["found"] else None for name, got in answered
        },
        "missing": [name for name, got in answered if not got["found"]],
    }
    if app.template is not None:
        result["template"] = _template(app.template, answer["template"])
    return result


async def hear(app, *, text, cursor, client_override=None) -> dict:
    said = _said(text)
    if not said:
        raise ReadError("nothing to read")
    shape = json.dumps(answer_model(app).model_json_schema())
    system = f"{_system('hear', app)}\n\nThe record's shape: {shape}"
    user = f"Cursor: {json.dumps(cursor)}\nUtterance: {said}"
    heard = await _parse(system, user, Heard, client_override)
    return {
        "updates": [
            {**_placed(update), "field": update["field"], "value": update["value"]}
            for update in heard["updates"]
        ],
        "cursor": None if heard["cursor"] is None else _placed(heard["cursor"]),
        "readback": heard["readback"],
    }
