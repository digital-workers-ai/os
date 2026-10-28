import json

import yaml
from pydantic import BaseModel

from app import llm, prompts
from app.config import settings
from app.engine import apps, ontology
from app.skills import catalog

SKILL = "dw-app"
DRAFT = "draft"
PERSON, BUILDER = "person", "builder"
OFF = "the builder is off: set BUILDER_ENABLED"


class BuilderError(RuntimeError):
    pass


class Missing(LookupError):
    pass


class Suggestion(BaseModel):
    app: str | None
    title: str
    reason: str


class Answer(BaseModel):
    reply: str
    questions: list[str]
    suggestions: list[Suggestion]
    draft: str | None


def ensure_on() -> None:
    if not settings.BUILDER_ENABLED:
        raise BuilderError(OFF)


def _skill_body() -> str:
    text = (catalog.SKILLS_DIR / SKILL / "SKILL.md").read_text()
    _front, body = text.split("\n---\n", 1)
    return body.strip()


def app_yaml(name) -> str:
    if name not in apps.names():
        raise Missing(f"no app named {name!r}")
    return (apps.APPS_DIR / name / "app.yaml").read_text()


def system_prompt(changing=None) -> str:
    parts = [
        prompts.text("app_builder", "turn"),
        _skill_body(),
        "## Apps already here\n\n" + ", ".join(apps.names()),
        "## Ontology entities\n\n" + ", ".join(ontology.load().entities),
    ]
    if changing is not None:
        parts.append(f"## The app to change: {changing}\n\n{app_yaml(changing)}")
    return "\n\n".join(parts)


def _said(message) -> dict:
    if message["role"] == PERSON:
        return {"role": "user", "content": message["text"]}
    answer = {
        "reply": message["text"],
        "questions": message["questions"],
        "suggestions": message["suggestions"],
        "draft": message["draft"],
        "problems": problems(message["draft"]),
    }
    return {"role": "assistant", "content": json.dumps(answer)}


def _mapping(draft: str) -> dict:
    try:
        raw = yaml.safe_load(draft)
    except yaml.YAMLError as exc:
        raise apps.AppError(f"the draft is not YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise apps.AppError("the draft is not a mapping")
    return raw


def parse_draft(draft: str) -> apps.App:
    return apps.parse(DRAFT, _mapping(draft))


def problems(draft) -> list[str]:
    if draft is None:
        return []
    try:
        parse_draft(draft)
    except apps.AppError as exc:
        return [str(exc)]
    return []


def title(draft) -> str | None:
    if draft is None:
        return None
    try:
        named = _mapping(draft).get("title")
    except apps.AppError:
        return None
    if not isinstance(named, str):
        return None
    return named.strip() or None


async def turn(messages, *, changing=None, client_override=None) -> dict:
    ensure_on()
    try:
        answer, _served_by = await llm.parse(
            model=settings.CUSTOM_MODEL,
            max_tokens=settings.CUSTOM_MAX_TOKENS,
            system=system_prompt(changing),
            messages=[_said(message) for message in messages],
            output_format=Answer,
            fallback=True,
            client_override=client_override,
        )
    except llm.LLMError as exc:
        raise BuilderError(str(exc)) from exc
    draft = answer.draft if (answer.draft or "").strip() else None
    here = apps.names()
    return {
        "reply": answer.reply,
        "questions": answer.questions,
        "suggestions": [
            suggestion.model_dump()
            for suggestion in answer.suggestions
            if suggestion.app is None or suggestion.app in here
        ],
        "draft": draft,
        "problems": problems(draft),
    }


def issue(drafted: apps.App, turns, draft: str, changing=None) -> tuple[str, str]:
    named = [] if changing is None else ["## App", changing]
    said = [f"### {turn['role'].title()}\n\n{turn['text']}" for turn in turns]
    body = "\n\n".join(
        [
            *named,
            "## Conversation",
            *said,
            "## Draft",
            f"```yaml\n{draft.strip()}\n```",
        ]
    )
    kind = "New" if changing is None else "Change"
    return f"{kind} app: {drafted.title}", body
