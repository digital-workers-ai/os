from app.sources.visibility import check_records, distinct

SOURCE = "chatgpt"


def _dict(value):
    return value if isinstance(value, dict) else {}


def _list(value):
    return value if isinstance(value, list) else []


def _text(value):
    return value.strip() if isinstance(value, str) else ""


def _message(response):
    choices = _list(_dict(response).get("choices"))
    first = choices[0] if choices else None
    return _dict(_dict(first).get("message"))


def _cited(message):
    for annotation in _list(message.get("annotations")):
        yield _dict(_dict(annotation).get("url_citation")).get("url")


def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type != "checks":
        return [payload]
    request = _dict(payload.get("request"))
    message = _message(payload.get("response"))
    return check_records(
        SOURCE,
        _text(request.get("query")),
        _text(request.get("checked_at")),
        payload,
        text=_text(message.get("content")),
        links=distinct(_cited(message)),
    )
