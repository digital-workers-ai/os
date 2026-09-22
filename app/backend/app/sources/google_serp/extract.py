from app.sources.visibility import check_records, distinct

ENGINES = {"searches": "google", "ai_overviews": "ai_overview"}


def _dict(value):
    return value if isinstance(value, dict) else {}


def _list(value):
    return value if isinstance(value, list) else []


def _text(value):
    return value.strip() if isinstance(value, str) else ""


def _lines(node):
    node = _dict(node)
    for key in ("title", "snippet"):
        line = _text(node.get(key))
        if line:
            yield line
    for row in _list(node.get("table")):
        cells = [str(cell) for cell in _list(row)]
        if cells:
            yield " | ".join(cells)
    for child in (*_list(node.get("list")), *_list(node.get("text_blocks"))):
        yield from _lines(child)


def _links(references):
    return distinct(_dict(reference).get("link") for reference in _list(references))


def _ranked(results):
    return [
        result
        for result in _list(results)
        if isinstance(result, dict) and isinstance(result.get("position"), int)
    ]


def reshape(object_type: str, payload: dict) -> list[dict]:
    engine = ENGINES.get(object_type)
    if engine is None:
        return [payload]
    request = _dict(payload.get("request"))
    query = _text(request.get("query"))
    checked_at = _text(request.get("checked_at"))
    if engine == "google":
        results = _list(_dict(payload.get("response")).get("organic_results"))
        check, *found = check_records(
            engine, query, checked_at, payload, results=_ranked(results)
        )
        check["_sources"] = len(results)
        return [check, *found]
    block = _dict(payload.get("ai_overview"))
    answer = "\n".join(_lines({"text_blocks": block.get("text_blocks")}))
    return check_records(
        engine,
        query,
        checked_at,
        payload,
        text=answer,
        links=_links(block.get("references")),
    )
