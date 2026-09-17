import base64

import openai

from app.config import settings
from app.llm import LLMError

_client = None


def client():
    global _client
    if _client is None:
        _client = openai.AsyncOpenAI()
    return _client


def reset() -> None:
    global _client
    _client = None


async def paint(
    prompt: str, size: str, *, model: str | None = None, client_override=None
) -> bytes:
    try:
        api = client_override or client()
        response = await api.images.generate(
            model=model or settings.PAINT_MODEL, prompt=prompt, size=size, n=1
        )
    except openai.OpenAIError as exc:
        raise LLMError(f"{type(exc).__name__}: {exc}") from exc
    data = response.data or []
    if not data or not data[0].b64_json:
        raise LLMError("the painter answered with no picture")
    return base64.b64decode(data[0].b64_json)
