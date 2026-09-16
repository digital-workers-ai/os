from app.engine import spy
from app.sources.visibility import check_records, distinct

SOURCE = "gemini"

REDIRECT_HOST = "vertexaisearch.cloud.google.com"


def _dict(value):
    return value if isinstance(value, dict) else {}


def _list(value):
    return value if isinstance(value, list) else []


def _str(value):
    return value if isinstance(value, str) else ""


def _message(payload):
    choices = _list(_dict(payload.get("response")).get("choices"))
    return _dict(_dict(choices[0] if choices else None).get("message"))


def _link(annotation):
    citation = _dict(_dict(annotation).get("url_citation"))
    url = _str(citation.get("url"))
    title = _str(citation.get("title"))
    if title and spy.host(url) == REDIRECT_HOST:
        return title
    return url


def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type != "checks":
        return [payload]
    request = _dict(payload.get("request"))
    message = _message(payload)
    return check_records(
        SOURCE,
        _str(request.get("query")),
        _str(request.get("checked_at")),
        payload,
        text=_str(message.get("content")),
        links=distinct(_link(a) for a in _list(message.get("annotations"))),
    )
