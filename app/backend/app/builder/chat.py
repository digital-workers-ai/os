import yaml
from pydantic import BaseModel

from app import llm, prompts
from app.config import settings
from app.engine import apps, ontology
from app.skills import catalog

SKILL = "dw-app"
DRAFT = "draft"
OFF = "the builder is off: set BUILDER_ENABLED"


class BuilderError(RuntimeError):
    pass


class Answer(BaseModel):
    reply: str
    questions: list[str]
    draft: str | None


def ensure_on() -> None:
    if not settings.BUILDER_ENABLED:
        raise BuilderError(OFF)


def _skill_body() -> str:
    text = (catalog.SKILLS_DIR / SKILL / "SKILL.md").read_text()
    _front, body = text.split("\n---\n", 1)
    return body.strip()


def system_prompt() -> str:
    return "\n\n".join(
        [
            prompts.text("app_builder", "turn"),
            _skill_body(),
            "## Apps already here\n\n" + ", ".join(apps.names()),
            "## Ontology entities\n\n" + ", ".join(ontology.load().entities),
        ]
    )


def conversation(messages) -> str:
    return "\n\n".join(f"{message['role']}: {message['text']}" for message in messages)


def parse_draft(draft: str) -> apps.App:
    try:
        raw = yaml.safe_load(draft)
    except yaml.YAMLError as exc:
        raise apps.AppError(f"the draft is not YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise apps.AppError("the draft is not a mapping")
    return apps.parse(DRAFT, raw)


def _problems(draft: str) -> list[str]:
    try:
        parse_draft(draft)
    except apps.AppError as exc:
        return [str(exc)]
    return []


async def turn(messages, *, client_override=None) -> dict:
    ensure_on()
    try:
        answer, _served_by = await llm.parse(
            model=settings.CUSTOM_MODEL,
            max_tokens=settings.CUSTOM_MAX_TOKENS,
            system=system_prompt(),
            user=conversation(messages),
            output_format=Answer,
            fallback=True,
            client_override=client_override,
        )
    except llm.LLMError as exc:
        raise BuilderError(str(exc)) from exc
    draft = answer.draft if (answer.draft or "").strip() else None
    return {
        "reply": answer.reply,
        "questions": answer.questions,
        "draft": draft,
        "problems": [] if draft is None else _problems(draft),
    }


def issue(app: apps.App, description: str, answers, draft: str) -> tuple[str, str]:
    listed = "\n".join(f"- {answer}" for answer in answers) or "None."
    body = "\n\n".join(
        [
            "## Description",
            description,
            "## Answers",
            listed,
            "## Draft",
            f"```yaml\n{draft.strip()}\n```",
        ]
    )
    return f"New app: {app.title}", body
