from app.sources.visibility import check_records, distinct

SOURCE = "claude"


def _dict(value):
    return value if isinstance(value, dict) else {}


def _list(value):
    return value if isinstance(value, list) else []


def _text(value):
    return value.strip() if isinstance(value, str) else ""


def _blocks(payload, kind):
    content = _list(_dict(payload.get("response")).get("content"))
    return [_dict(block) for block in content if _dict(block).get("type") == kind]


def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type != "checks":
        return [payload]
    request = _dict(payload.get("request"))
    texts = _blocks(payload, "text")
    answer = "\n".join(
        block["text"] for block in texts if isinstance(block.get("text"), str)
    )
    cited = [
        _dict(citation).get("url")
        for block in texts
        for citation in _list(block.get("citations"))
    ]
    read = [
        _dict(result).get("url")
        for block in _blocks(payload, "web_search_tool_result")
        for result in _list(block.get("content"))
    ]
    return check_records(
        SOURCE,
        _text(request.get("query")),
        _text(request.get("checked_at")),
        payload,
        text=answer,
        links=distinct([*cited, *read]),
    )
