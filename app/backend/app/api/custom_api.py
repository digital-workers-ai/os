import base64
import dataclasses
import uuid
from contextlib import contextmanager
from typing import Annotated

from fastapi import Depends, HTTPException, Response
from pydantic import AfterValidator, BaseModel

from app.api.routers import custom as router
from app.custom import access, reader, records, scripts, transcribe
from app.db import get_session
from app.engine import apps

NOT_FOUND = {404: {"description": "no such app, record, field or file"}}
FORBIDDEN = {403: {"description": "the actor's roles may not open the app"}}
CANNOT = {409: {"description": "reading, transcribing or the app's script failed"}}
TOO_LARGE = {413: {"description": "past a limit on photos, pages, seconds or bytes"}}
OPENED = {**NOT_FOUND, **FORBIDDEN}
ANSWERS = (
    (records.Missing, 404),
    (records.Refused, 422),
    (records.TooLarge, 413),
    (reader.ReadError, 409),
    (transcribe.TranscribeError, 409),
    (scripts.ScriptError, 409),
)


def _decoded(text: str) -> bytes:
    return base64.b64decode(text, validate=True)


Base64 = Annotated[str, AfterValidator(_decoded)]


class FileBody(BaseModel):
    name: str
    media_type: str
    data: Base64


class ClipBody(BaseModel):
    media_type: str
    data: Base64


class CreateBody(BaseModel):
    files: list[FileBody] = []
    scan: str | None = None
    audio: ClipBody | None = None


class SaveBody(BaseModel):
    fields: dict


class HearBody(BaseModel):
    audio: ClipBody
    cursor: dict | None = None


@contextmanager
def _answering():
    try:
        yield
    except tuple(kind for kind, _status in ANSWERS) as exc:
        status = next(status for kind, status in ANSWERS if isinstance(exc, kind))
        raise HTTPException(status_code=status, detail=str(exc)) from exc


def _opened(name: str) -> apps.App:
    try:
        app = apps.load(name)
    except apps.AppError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    roles = access.roles()
    if not access.may_open(app, roles):
        raise HTTPException(
            status_code=403, detail=f"the roles {list(roles)} may not open {name}"
        )
    return app


async def _record_app(session, record_id: uuid.UUID) -> apps.App:
    with _answering():
        name = await records.app_of(session, record_id)
    return _opened(name)


def _summary(app) -> dict:
    return {
        "name": app.name,
        "title": app.title,
        "description": app.description,
        "input": list(app.inputs),
        "roles": list(app.roles),
        "lands_as": app.lands_as,
        "script": app.script is not None,
        "screen": any(field.type == "screen" for field in records.every_field(app)),
    }


def _clip(body: ClipBody | None):
    return None if body is None else (body.media_type, body.data)


@router.get("/apps")
async def list_apps():
    roles = access.roles()
    shipped = sorted(apps.apps().items())
    return [_summary(app) for _name, app in shipped if access.may_open(app, roles)]


@router.get("/apps/{app}", responses=OPENED)
async def get_app(app: str):
    opened = _opened(app)
    template = opened.template
    return {
        **_summary(opened),
        "fields": [dataclasses.asdict(field) for field in opened.fields],
        "template": None if template is None else dataclasses.asdict(template),
    }


@router.get("/apps/{app}/lookup/{field}", responses=OPENED)
async def lookup(app: str, field: str, q: str = "", session=Depends(get_session)):
    opened = _opened(app)
    with _answering():
        found = await records.lookup(session, opened, field, q)
    return found


@router.post(
    "/apps/{app}/records",
    status_code=201,
    responses={**OPENED, **CANNOT, **TOO_LARGE},
)
async def create_record(app: str, body: CreateBody, session=Depends(get_session)):
    opened = _opened(app)
    with _answering():
        made = await records.create(
            session,
            opened,
            files=[(file.name, file.media_type, file.data) for file in body.files],
            scan=body.scan,
            audio=_clip(body.audio),
            actor=access.actor(),
        )
    await session.commit()
    return made


@router.put("/records/{id}", responses={**OPENED, **CANNOT})
async def save_record(id: uuid.UUID, body: SaveBody, session=Depends(get_session)):
    opened = await _record_app(session, id)
    with _answering():
        detail = await records.save(
            session, opened, id, body.fields, actor=access.actor()
        )
    await session.commit()
    return detail


@router.post("/records/{id}/hear", responses={**OPENED, **CANNOT, **TOO_LARGE})
async def hear_record(id: uuid.UUID, body: HearBody, session=Depends(get_session)):
    opened = await _record_app(session, id)
    with _answering():
        heard = await records.hear(
            session,
            opened,
            id,
            _clip(body.audio),
            cursor=body.cursor,
            actor=access.actor(),
        )
    await session.commit()
    return heard


@router.post("/records/{id}/files", status_code=201, responses={**OPENED, **TOO_LARGE})
async def attach_file(id: uuid.UUID, body: FileBody, session=Depends(get_session)):
    opened = await _record_app(session, id)
    with _answering():
        attached = await records.attach(
            session,
            opened,
            id,
            body.name,
            body.media_type,
            body.data,
            actor=access.actor(),
        )
    await session.commit()
    return attached


@router.get("/records", responses=OPENED)
async def list_records(app: str, session=Depends(get_session)):
    opened = _opened(app)
    return await records.listing(session, opened.name)


@router.get("/records/{id}", responses=OPENED)
async def get_record(id: uuid.UUID, session=Depends(get_session)):
    await _record_app(session, id)
    detail = await records.view(session, id, actor=access.actor())
    await session.commit()
    return detail


@router.get("/records/{id}/files/{path:path}", responses=OPENED)
async def get_record_file(id: uuid.UUID, path: str, session=Depends(get_session)):
    await _record_app(session, id)
    with _answering():
        data, media_type = await records.file_bytes(session, id, path)
    return Response(content=data, media_type=media_type)


@router.delete("/records/{id}", responses=OPENED)
async def remove_record(id: uuid.UUID, session=Depends(get_session)):
    await _record_app(session, id)
    with _answering():
        await records.remove(session, id, actor=access.actor())
    await session.commit()
    return {"removed": True}
