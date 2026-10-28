import re
import struct
import uuid
from datetime import UTC
from pathlib import Path
from typing import NamedTuple

from sqlalchemy import String, cast, exists, func, select
from sqlalchemy.orm import aliased

from app import clock, media, store
from app.api.entities_api import LABEL_ATTRS, _label
from app.config import settings
from app.custom import audit, reader, scripts, transcribe
from app.engine import apps
from app.models import (
    CustomRecord,
    CustomRecordFile,
    EngineRun,
    EntityCanonical,
    FactCurrent,
    RawEvent,
)

SOURCE = "custom"
MAX_PHOTOS = 10
MAX_PDF_PAGES = 100
MAX_CLIP_SECONDS = 60
MAX_REQUEST_BYTES = 32 * 1024 * 1024
MAX_MATCHES = 20
PDF = "application/pdf"
PHOTO_TYPES = ("image/jpeg", "image/png", "image/webp")
FILE_TYPES = (*PHOTO_TYPES, PDF)
CLIP_SUFFIXES = {"audio/webm": "webm", "audio/mp4": "m4a", "audio/wav": "wav"}
LABELLED = ("one_of", "many_of")
TEMPLATE = "template"
TEMPLATE_PARTS = ("rows", "cells", "items")
CURRENCY = "USD"
STAMP = "%Y-%m-%dT%H:%M:%SZ"
PAGE = re.compile(rb"/Type\s*/Page\b")
SEGMENT = b"\x18\x53\x80\x67"
INFO = b"\x15\x49\xa9\x66"
TIMECODE_SCALE = b"\x2a\xd7\xb1"
DURATION = b"\x44\x89"
DEFAULT_TIMECODE_SCALE = (1_000_000).to_bytes(3)
FLOATS = {4: ">f", 8: ">d"}


class Missing(LookupError):
    pass


class Refused(ValueError):
    pass


class TooLarge(ValueError):
    pass


class Sent(NamedTuple):
    path: str
    media_type: str
    data: bytes
    kind: str


def _ebml(data: bytes) -> dict[bytes, bytes]:
    found = {}
    at = 0
    while at < len(data):
        sized = at + 9 - data[at].bit_length()
        width = 9 - int.from_bytes(data[sized : sized + 1]).bit_length()
        size = int.from_bytes(data[sized : sized + width]) & ((1 << 7 * width) - 1)
        body = sized + width
        found.setdefault(data[at:sized], data[body : body + size])
        at = body + size
    return found


def _boxes(data: bytes) -> dict[bytes, bytes]:
    found = {}
    at = 0
    while at + 8 <= len(data):
        size = max(int.from_bytes(data[at : at + 4]), 8)
        found.setdefault(data[at + 4 : at + 8], data[at + 8 : at + size])
        at += size
    return found


def _chunks(data: bytes) -> dict[bytes, bytes]:
    found = {}
    at = 12
    while at + 8 <= len(data):
        size = int.from_bytes(data[at + 4 : at + 8], "little")
        found.setdefault(data[at : at + 4], data[at + 8 : at + 8 + size])
        at += 8 + size + size % 2
    return found


def _webm_seconds(data: bytes) -> float | None:
    info = _ebml(_ebml(_ebml(data).get(SEGMENT, b"")).get(INFO, b""))
    duration = info.get(DURATION, b"")
    scale = int.from_bytes(info.get(TIMECODE_SCALE, DEFAULT_TIMECODE_SCALE))
    width = FLOATS.get(len(duration))
    return None if width is None else struct.unpack(width, duration)[0] * scale / 1e9


def _mp4_seconds(data: bytes) -> float | None:
    header = _boxes(_boxes(data).get(b"moov", b"")).get(b"mvhd", b"")
    wide = header[:1] == b"\x01"
    scale_at = 20 if wide else 12
    scale = int.from_bytes(header[scale_at : scale_at + 4])
    stated = header[scale_at + 4 : scale_at + (12 if wide else 8)]
    duration = int.from_bytes(stated)
    known = scale and duration != (1 << 8 * len(stated)) - 1
    return duration / scale if known else None


def _wav_seconds(data: bytes) -> float | None:
    chunks = _chunks(data)
    rate = int.from_bytes(chunks.get(b"fmt ", b"")[8:12], "little")
    return len(chunks.get(b"data", b"")) / rate if rate else None


CLIP_SECONDS = {
    "audio/webm": _webm_seconds,
    "audio/mp4": _mp4_seconds,
    "audio/wav": _wav_seconds,
}


def every_field(app) -> list:
    template = app.template
    parts = () if template is None else (template.rows, template.cells, template.items)
    tops = [*app.fields, *(field for part in parts if part for field in part["fields"])]
    return [field for top in tops for field in (top, *top.fields)]


def _named(name: str) -> str:
    try:
        return media.relative(name)
    except media.MediaError as exc:
        raise Refused(str(exc)) from exc


def _sniffed(name: str, media_type: str, data: bytes, accepted) -> None:
    found = media.sniff(data)
    if media_type not in accepted or found != media_type:
        raise Refused(
            f"{name} is sent as {media_type}, but its bytes read as "
            f"{found or 'no type a record keeps'}; this takes {', '.join(accepted)}"
        )


def _within_request(total: int) -> None:
    if total > MAX_REQUEST_BYTES:
        raise TooLarge(
            f"the request carries {total} bytes, over the {MAX_REQUEST_BYTES} one "
            "request may carry"
        )


def _photo_limit(photos: int) -> None:
    if photos > MAX_PHOTOS:
        raise TooLarge(
            f"{photos} photos would be on the record, and a record keeps at most "
            f"{MAX_PHOTOS}"
        )


def _pdf_limit(pdfs: list[bytes]) -> None:
    if len(pdfs) > 1:
        raise TooLarge(f"{len(pdfs)} PDFs came, and a record keeps one")
    pages = sum(len(PAGE.findall(pdf)) for pdf in pdfs)
    if pages > MAX_PDF_PAGES:
        raise TooLarge(
            f"the PDF has {pages} pages, over the {MAX_PDF_PAGES} a record keeps"
        )


def _clip(audio) -> None:
    media_type, data = audio
    _sniffed("the clip", media_type, data, tuple(CLIP_SUFFIXES))
    seconds = CLIP_SECONDS[media_type](data)
    if seconds is not None and seconds > MAX_CLIP_SECONDS:
        raise TooLarge(
            f"the clip runs {seconds:.1f} seconds, over the {MAX_CLIP_SECONDS} "
            "one clip may run"
        )


def _kind(app, path: str, media_type: str) -> str:
    if media_type == PDF:
        return "pdf"
    screens = {field.name for field in every_field(app) if field.type == "screen"}
    return "signature" if Path(path).stem in screens else "photo"


def _checked(app, name: str, media_type: str, data: bytes) -> Sent:
    path = _named(name)
    _sniffed(name, media_type, data, FILE_TYPES)
    return Sent(path, media_type, data, _kind(app, path, media_type))


def _labels(field) -> tuple[str, ...]:
    return tuple(label for label, _meaning in field.labels)


def _check_value(field, value, where: str) -> None:
    chosen = value if field.type == "many_of" else [value]
    unknown = [
        label
        for label in chosen or ()
        if field.type in LABELLED and label is not None and label not in _labels(field)
    ]
    if unknown:
        raise Refused(f"{where} takes {list(_labels(field))}, not {unknown}")
    rows = value if field.type == "list" else None
    for index, row in enumerate(rows or ()):
        _check_fields(field.fields, row, f"{where}.{index}.")


def _check_fields(fields, values: dict, where: str) -> None:
    named = {field.name: field for field in fields}
    for name, value in values.items():
        if name not in named:
            raise Refused(
                f"{where}{name} is not a field here; the fields are {list(named)}"
            )
        _check_value(named[name], value, f"{where}{name}")


def _template_parts(template) -> dict:
    if template.kind == "grid":
        rows, columns = template.rows["values"], template.columns["values"]
        cells = tuple(f"{row}:{column}" for row in rows for column in columns)
        return {
            "rows": (rows, template.rows["fields"]),
            "cells": (cells, template.cells["fields"]),
        }
    items = tuple(
        f"{section}:{item}"
        for section, names in template.sections.items()
        for item in names
    )
    return {"items": (items, template.items["fields"])}


def _check_template(app, given: dict) -> None:
    if app.template is None:
        raise Refused(f"template: {app.name} has no template")
    parts = _template_parts(app.template)
    for part, entries in given.items():
        if part not in parts:
            raise Refused(
                f"template.{part} is not part of a {app.template.kind}; "
                f"its parts are {list(parts)}"
            )
        keys, fields = parts[part]
        for key, values in (entries or {}).items():
            if key not in keys:
                raise Refused(f"template.{part} has no {key!r}")
            _check_fields(fields, values, f"template.{part}.{key}.")


def _values(fields: dict) -> dict:
    return {name: value for name, value in fields.items() if name != TEMPLATE}


def check(app, fields: dict) -> None:
    _check_fields(app.fields, _values(fields), "")
    if fields.get(TEMPLATE) is not None:
        _check_template(app, fields[TEMPLATE])


def _stamp(when) -> str:
    return when.astimezone(UTC).strftime(STAMP)


def payload(app, record, fields: dict, files: list[dict]) -> dict:
    saved = {
        "record": str(record.id),
        "app": app.name,
        "recorded_at": _stamp(record.created_at),
        "recorded_by": record.recorded_by,
        "removed": False,
        "files": files,
        "fields": _values(fields),
    }
    if any(field.type == "money" for field in every_field(app)):
        saved["currency"] = CURRENCY
    if "voice" in app.inputs:
        saved["transcript"] = record.transcript
    if app.template is not None:
        empty = {part: {} for part in TEMPLATE_PARTS}
        saved[TEMPLATE] = {**empty, **(fields.get(TEMPLATE) or {})}
    return saved


def _shown(saved: dict) -> dict:
    template = {TEMPLATE: saved[TEMPLATE]} if TEMPLATE in saved else {}
    return {**saved.get("fields", {}), **template}


async def _record(session, record_id) -> CustomRecord:
    record = await session.get(CustomRecord, record_id)
    if record is None:
        raise Missing(f"no record {record_id}")
    return record


async def _live(session, record_id) -> CustomRecord:
    record = await _record(session, record_id)
    if record.removed_at is not None:
        raise Missing(f"record {record_id} was removed")
    return record


async def app_of(session, record_id) -> str:
    return (await _record(session, record_id)).app


async def _files(session, record_id) -> list[dict]:
    found = await session.execute(
        select(CustomRecordFile)
        .where(CustomRecordFile.record_id == record_id)
        .order_by(CustomRecordFile.path)
    )
    return [
        {"path": file.path, "media_type": file.media_type, "kind": file.kind}
        for file in found.scalars()
    ]


async def _store(session, record_id, sent: Sent) -> None:
    media.write_record(record_id, sent.path, sent.data)
    row = await session.scalar(
        select(CustomRecordFile).where(
            CustomRecordFile.record_id == record_id,
            CustomRecordFile.path == sent.path,
        )
    )
    row = row or CustomRecordFile(record_id=record_id, path=sent.path)
    row.media_type, row.bytes, row.kind = sent.media_type, len(sent.data), sent.kind
    row.created_at = clock.now()
    session.add(row)
    await session.flush()


async def _store_clip(session, record_id, audio) -> None:
    media_type, data = audio
    clips = await session.scalar(
        select(func.count())
        .select_from(CustomRecordFile)
        .where(
            CustomRecordFile.record_id == record_id, CustomRecordFile.kind == "audio"
        )
    )
    path = f"clip-{clips + 1}.{CLIP_SUFFIXES[media_type]}"
    await _store(session, record_id, Sent(path, media_type, data, "audio"))


async def _transcribed(app, audio) -> str | None:
    if settings.TRANSCRIBE_ENABLED and audio is not None:
        media_type, data = audio
        return await transcribe.transcribe(app, data, media_type)
    return None


async def _read(app, sent: list[Sent], transcript: str | None) -> dict:
    if settings.CUSTOM_ENABLED and (sent or transcript):
        files = [(file.media_type, file.data) for file in sent]
        return await reader.read(app, files=files, text=transcript)
    return {"fields": {}, "missing": []}


def checked(app, files, audio=None) -> list[Sent]:
    sent = [_checked(app, *file) for file in files]
    if audio is not None:
        _clip(audio)
    _photo_limit(sum(file.kind == "photo" for file in sent))
    _pdf_limit([file.data for file in sent if file.kind == "pdf"])
    clip_bytes = 0 if audio is None else len(audio[1])
    _within_request(sum(len(file.data) for file in sent) + clip_bytes)
    return sent


async def create(session, app, *, files, scan, audio, actor) -> dict:
    sent = checked(app, files, audio)
    transcript = await _transcribed(app, audio)
    reading = await _read(app, sent, transcript)
    scanned = {
        field.name: scan for field in app.fields if field.from_scan and scan is not None
    }
    record = CustomRecord(
        id=uuid.uuid4(),
        app=app.name,
        recorded_by=actor,
        transcript=transcript,
        created_at=clock.now(),
    )
    session.add(record)
    await session.flush()
    for file in sent:
        await _store(session, record.id, file)
    if audio is not None:
        await _store_clip(session, record.id, audio)
    await audit.note(session, record.id, "create", actor)
    return {
        "id": str(record.id),
        "app": app.name,
        "fields": {**reading["fields"], **scanned},
        "missing": [name for name in reading["missing"] if name not in scanned],
        "files": await _files(session, record.id),
        "transcript": transcript,
    }


async def _rebuilt_since(session, saved_at) -> bool:
    return await session.scalar(
        select(exists().where(EngineRun.ok.is_(True), EngineRun.created_at > saved_at))
    )


async def _entity(session, app, record, fields: dict) -> dict | None:
    found = await session.scalar(
        select(EntityCanonical.canonical_id).where(
            EntityCanonical.anchor_key == f"{SOURCE}|{app.lands_as}|{record.id}"
        )
    )
    if found is None:
        return None
    facts = await session.execute(
        select(FactCurrent.attr, FactCurrent.value).where(
            FactCurrent.canonical_id == found, FactCurrent.attr.in_(LABEL_ATTRS)
        )
    )
    named = next(
        (
            fields[field.name]
            for field in app.fields
            if field.type == "text" and fields.get(field.name)
        ),
        None,
    )
    return {
        "type": app.lands_as,
        "id": str(found),
        "label": _label(named, dict(facts.all())),
    }


async def _latest(session, record) -> dict:
    found = await session.scalar(
        select(RawEvent.raw_payload)
        .where(
            RawEvent.source == SOURCE,
            RawEvent.object_type == record.app,
            RawEvent.source_id == str(record.id),
            RawEvent.raw_payload.contains({"removed": False}),
        )
        .order_by(RawEvent.seq.desc())
        .limit(1)
    )
    return found or {}


async def _detail(session, app, record) -> dict:
    saved = await _latest(session, record)
    counted = record.saved_at is not None and await _rebuilt_since(
        session, record.saved_at
    )
    return {
        "id": str(record.id),
        "app": record.app,
        "fields": _shown(saved),
        "files": await _files(session, record.id),
        "history": await audit.history(session, record.id),
        "counted": counted,
        "entity": await _entity(session, app, record, saved.get("fields", {})),
        "removed": record.removed_at is not None,
    }


async def save(session, app, record_id, fields: dict, *, actor) -> dict:
    record = await _live(session, record_id)
    check(app, fields)
    if app.script is not None:
        ctx = scripts.Context(session, app, record_id=record.id)
        fields = {**fields, **(await scripts.run(app, _values(fields), ctx))}
    action = "save" if record.saved_at is None else "edit"
    record.saved_at = record.saved_at or clock.now()
    files = await _files(session, record.id)
    await store.save_raw(
        session,
        source=SOURCE,
        object_type=app.name,
        source_id=str(record.id),
        raw_payload=payload(app, record, fields, files),
    )
    await audit.note(session, record.id, action, actor)
    return await _detail(session, app, record)


async def view(session, record_id, *, actor) -> dict:
    record = await _record(session, record_id)
    await audit.note(session, record.id, "view", actor)
    return await _detail(session, apps.load(record.app), record)


def _saved_payloads(app_name: str):
    return (
        select(RawEvent.source_id, RawEvent.raw_payload)
        .where(RawEvent.source == SOURCE, RawEvent.object_type == app_name)
        .distinct(RawEvent.source_id)
        .order_by(RawEvent.source_id, RawEvent.seq.desc())
        .subquery()
    )


async def _listed(session, latest, *conditions) -> list[dict]:
    found = await session.execute(
        select(
            CustomRecord.id,
            CustomRecord.app,
            CustomRecord.saved_at,
            latest.c.raw_payload,
        )
        .join(latest, latest.c.source_id == cast(CustomRecord.id, String))
        .where(
            CustomRecord.saved_at.is_not(None),
            CustomRecord.removed_at.is_(None),
            *conditions,
        )
        .order_by(
            CustomRecord.saved_at.desc(),
            CustomRecord.created_at.desc(),
            CustomRecord.id,
        )
    )
    return [
        {
            "id": str(record_id),
            "app": app_name,
            "fields": _shown(saved),
            "saved_at": saved_at.isoformat(),
        }
        for record_id, app_name, saved_at, saved in found
    ]


async def listing(session, app_name: str) -> list[dict]:
    return await _listed(session, _saved_payloads(app_name))


async def _history(session, app, field, q: str) -> list[dict]:
    latest = _saved_payloads(app.name)
    value = latest.c.raw_payload["fields"][field.name].astext
    return await _listed(session, latest, value == q)


def _lookup_field(app, path: str):
    fields, found = app.fields, None
    for name in path.split("."):
        found = next((field for field in fields if field.name == name), None)
        fields = () if found is None else found.fields
    if found is None or found.type != "lookup":
        raise Missing(f"{app.name} has no lookup field {path!r}")
    return found


async def lookup(session, app, path: str, q: str) -> dict:
    field = _lookup_field(app, path)
    if not q.strip():
        return {"matches": [], "history": []}
    by, name = aliased(FactCurrent), aliased(FactCurrent)
    label = func.coalesce(name.value, by.value)
    matching = by.value == q if field.from_scan else label.icontains(q, autoescape=True)
    found = await session.execute(
        select(by.value, label)
        .select_from(by)
        .outerjoin(name, (name.canonical_id == by.canonical_id) & (name.attr == "name"))
        .where(
            by.entity_type == field.entity, by.attr == (field.by or "name"), matching
        )
        .order_by(label, by.value)
        .limit(MAX_MATCHES)
    )
    history = await _history(session, app, field, q) if field.history else []
    return {
        "matches": [{"value": value, "label": shown} for value, shown in found],
        "history": history,
    }


async def remove(session, record_id, *, actor) -> None:
    record = await _live(session, record_id)
    await store.save_raw(
        session,
        source=SOURCE,
        object_type=record.app,
        source_id=str(record.id),
        raw_payload={
            "record": str(record.id),
            "app": record.app,
            "removed": True,
            "recorded_at": _stamp(record.created_at),
            "recorded_by": record.recorded_by,
        },
    )
    record.removed_at = clock.now()
    await audit.note(session, record.id, "remove", actor)


async def _heard(app, transcript: str, cursor) -> dict:
    if not transcript.strip():
        return {"updates": [], "cursor": cursor, "readback": ""}
    return await reader.hear(app, text=transcript, cursor=cursor)


async def hear(session, app, record_id, audio, *, cursor, actor) -> dict:
    record = await _live(session, record_id)
    media_type, data = audio
    _clip(audio)
    _within_request(len(data))
    transcript = await transcribe.transcribe(app, data, media_type)
    heard = await _heard(app, transcript, cursor)
    await _store_clip(session, record.id, audio)
    said = "\n".join(part for part in (record.transcript, transcript) if part)
    record.transcript = said or None
    await session.flush()
    return {"transcript": transcript, **heard}


async def attach(session, app, record_id, name, media_type, data, *, actor) -> dict:
    record = await _live(session, record_id)
    path = _named(name)
    _sniffed(name, media_type, data, PHOTO_TYPES)
    _within_request(len(data))
    kind = _kind(app, path, media_type)
    kept = {
        file["path"]
        for file in await _files(session, record.id)
        if file["kind"] == "photo"
    }
    _photo_limit(len(kept | ({path} if kind == "photo" else set())))
    await _store(session, record.id, Sent(path, media_type, data, kind))
    return {"path": path, "media_type": media_type, "kind": kind}


async def file_bytes(session, record_id, path: str) -> tuple[bytes, str]:
    record = await _record(session, record_id)
    row = await session.scalar(
        select(CustomRecordFile).where(
            CustomRecordFile.record_id == record.id, CustomRecordFile.path == path
        )
    )
    if row is None:
        raise Missing(f"record {record_id} has no file {path!r}")
    return media.read_record(record.id, row.path), row.media_type
