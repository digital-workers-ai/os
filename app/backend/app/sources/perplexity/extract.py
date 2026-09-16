from app.sources.visibility import check_records, distinct

SOURCE = "perplexity"


def _dict(value):
    return value if isinstance(value, dict) else {}


def _list(value):
    return value if isinstance(value, list) else []


def _text(value):
    return value.strip() if isinstance(value, str) else ""


def _message(response):
    choices = _list(_dict(response).get("choices"))
    return _dict(_dict(choices[0] if choices else None).get("message"))


def _urls(annotations):
    return distinct(
        _dict(_dict(annotation).get("url_citation")).get("url")
        for annotation in _list(annotations)
    )


def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type != "checks":
        return [payload]
    request = _dict(payload.get("request"))
    message = _message(payload.get("response"))
    content = message.get("content")
    return check_records(
        SOURCE,
        _text(request.get("query")),
        _text(request.get("checked_at")),
        payload,
        text=content if isinstance(content, str) else "",
        links=_urls(message.get("annotations")),
    )
