import anthropic


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
