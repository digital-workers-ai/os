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


async def embed(
    texts: list[str], *, model: str | None = None, client_override=None
) -> list[list[float]]:
    try:
        api = client_override or client()
        response = await api.embeddings.create(
            model=model or settings.EMBEDDING_MODEL,
            input=texts,
            dimensions=settings.EMBEDDING_DIMS,
        )
    except Exception as exc:
        raise LLMError(f"{type(exc).__name__}: {exc}") from exc
    return [item.embedding for item in response.data]
