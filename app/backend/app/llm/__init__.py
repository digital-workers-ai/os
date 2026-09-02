import anthropic

from app.config import settings


class LLMError(RuntimeError):
    pass


_client = None


def client():
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic()
    return _client


def reset() -> None:
    global _client
    _client = None


async def complete(
    system: str,
    user: str,
    *,
    model: str | None = None,
    max_tokens: int | None = None,
    client_override=None,
) -> str:
    api = client_override or client()
    try:
        response = await api.messages.create(
            model=model or settings.COACHING_MODEL,
            max_tokens=max_tokens or settings.COACHING_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    except anthropic.APIError as exc:
        raise LLMError(f"{type(exc).__name__}: {exc}") from exc

    if getattr(response, "stop_reason", None) == "refusal":
        raise LLMError("the model declined to answer")
    text = "".join(
        block.text
        for block in response.content
        if getattr(block, "type", None) == "text"
    )
    if not text.strip():
        raise LLMError(
            f"empty response (stop_reason={getattr(response, 'stop_reason', None)!r})"
        )
    return text


async def parse(
    *, model, max_tokens, system, user, output_format, client_override=None
):
    api = client_override or client()
    try:
        response = await api.messages.parse(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=output_format,
        )
    except anthropic.APIError as exc:
        raise LLMError(f"{type(exc).__name__}: {exc}") from exc
    except Exception as exc:
        raise LLMError(f"{type(exc).__name__}: {exc}") from exc

    if getattr(response, "stop_reason", None) == "refusal":
        raise LLMError("the model declined to answer")
    parsed = getattr(response, "parsed_output", None)
    if parsed is None:
        raise LLMError(
            f"no parsed output (stop_reason={getattr(response, 'stop_reason', None)!r})"
        )
    return parsed, getattr(response, "model", model)
