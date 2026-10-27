from typing import Annotated, Literal

from fastapi import HTTPException
from pydantic import Base64Bytes, BaseModel, Field, StringConstraints

from app.api.routers import builder as router
from app.builder import chat, github
from app.custom import reader
from app.engine import apps

CANNOT_ANSWER = {409: {"description": "the builder is off or cannot answer"}}
NOT_FILED = {502: {"description": "GitHub did not file the issue"}}


class Message(BaseModel):
    role: Literal["person", "builder"]
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class TurnsBody(BaseModel):
    messages: Annotated[list[Message], Field(min_length=1)]


class Sample(BaseModel):
    media_type: str
    data: Base64Bytes


class TryBody(BaseModel):
    draft: str
    files: list[Sample] = []
    text: str | None = None


class SubmitBody(BaseModel):
    description: str
    answers: list[str]
    draft: str


def _drafted(draft) -> apps.App:
    try:
        chat.ensure_on()
    except chat.BuilderError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    try:
        return chat.parse_draft(draft)
    except apps.AppError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/turns", responses=CANNOT_ANSWER)
async def turns(body: TurnsBody):
    try:
        return await chat.turn([message.model_dump() for message in body.messages])
    except chat.BuilderError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/try", responses=CANNOT_ANSWER)
async def try_draft(body: TryBody):
    definition = _drafted(body.draft)
    files = [(sample.media_type, sample.data) for sample in body.files]
    try:
        return await reader.read(definition, files=files, text=body.text)
    except reader.ReadError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/submit", responses={**CANNOT_ANSWER, **NOT_FILED})
async def submit(body: SubmitBody):
    title, text = chat.issue(
        _drafted(body.draft), body.description, body.answers, body.draft
    )
    try:
        return await github.file_issue(title, text)
    except github.GitHubError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
