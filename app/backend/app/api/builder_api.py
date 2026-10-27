import uuid
from contextlib import contextmanager
from typing import Annotated

from fastapi import Depends, HTTPException
from pydantic import Base64Bytes, BaseModel, StringConstraints

from app.api.routers import builder as router
from app.builder import chat, github, threads
from app.custom import reader, records
from app.db import get_session
from app.engine import apps

NOT_FOUND = {404: {"description": "no such thread or app"}}
CANNOT_ANSWER = {
    409: {"description": "the builder is off, cannot answer, has no draft or filed"}
}
NOT_FILED = {502: {"description": "GitHub did not file the issue"}}
TOO_LARGE = {413: {"description": "past a limit on photos, pages or bytes"}}
ANSWERS = (
    (chat.Missing, 404),
    (chat.BuilderError, 409),
    (reader.ReadError, 409),
    (apps.AppError, 422),
    (records.Refused, 422),
    (records.TooLarge, 413),
    (github.GitHubError, 502),
)


class ThreadBody(BaseModel):
    app: str | None = None


class TextBody(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Sample(BaseModel):
    name: str
    media_type: str
    data: Base64Bytes


class TryBody(BaseModel):
    files: list[Sample] = []
    text: str | None = None


@contextmanager
def _answering():
    try:
        yield
    except tuple(kind for kind, _status in ANSWERS) as exc:
        status = next(status for kind, status in ANSWERS if isinstance(exc, kind))
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.post("/threads", status_code=201, responses={**NOT_FOUND, **CANNOT_ANSWER})
async def create_thread(body: ThreadBody | None = None, session=Depends(get_session)):
    with _answering():
        made = await threads.create(session, None if body is None else body.app)
    await session.commit()
    return made


@router.get("/threads")
async def list_threads(session=Depends(get_session)):
    return await threads.threads(session)


@router.get("/threads/{id}", responses=NOT_FOUND)
async def get_thread(id: uuid.UUID, session=Depends(get_session)):
    with _answering():
        return await threads.thread(session, id)


@router.post("/threads/{id}/turns", responses={**NOT_FOUND, **CANNOT_ANSWER})
async def take_turn(id: uuid.UUID, body: TextBody, session=Depends(get_session)):
    with _answering():
        said = await threads.say(session, id, body.text)
    await session.commit()
    return said


@router.post("/threads/{id}/try", responses={**NOT_FOUND, **CANNOT_ANSWER, **TOO_LARGE})
async def try_draft(id: uuid.UUID, body: TryBody, session=Depends(get_session)):
    sent = [(sample.name, sample.media_type, sample.data) for sample in body.files]
    with _answering():
        drafted = await threads.drafted(session, id)
        files = [
            (file.media_type, file.data) for file in records.checked(drafted, sent)
        ]
        return await reader.read(drafted, files=files, text=body.text)


@router.post(
    "/threads/{id}/submit", responses={**NOT_FOUND, **CANNOT_ANSWER, **NOT_FILED}
)
async def submit(id: uuid.UUID, session=Depends(get_session)):
    with _answering():
        filed = await threads.file(session, id)
    await session.commit()
    return filed


@router.get("/apps/{app}/yaml", responses=NOT_FOUND)
async def app_yaml(app: str):
    with _answering():
        return {"yaml": chat.app_yaml(app)}
