import os

import httpx

from app.config import RERANK_CREDENTIAL_ENV, settings
from app.llm import LLMError

RERANK_URL = "https://api.zeroentropy.dev/v1/models/rerank"

_client = None


def client():
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=30)
    return _client


def reset() -> None:
    global _client
    _client = None


async def rerank(
    query: str,
    documents: list[str],
    *,
    model: str | None = None,
    client_override=None,
) -> list[float]:
    body = {
        "model": model or settings.RERANK_MODEL,
        "query": query,
        "documents": documents,
    }
    headers = {"Authorization": f"Bearer {os.environ.get(RERANK_CREDENTIAL_ENV, '')}"}
    try:
        api = client_override or client()
        response = await api.post(RERANK_URL, json=body, headers=headers)
        response.raise_for_status()
        results = response.json()["results"]
    except Exception as exc:
        raise LLMError(f"{type(exc).__name__}: {exc}") from exc
    scores = [0.0] * len(documents)
    for item in results:
        scores[item["index"]] = float(item["relevance_score"])
    return scores
