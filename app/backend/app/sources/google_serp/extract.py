from app.engine import spy

SOURCE = "google_serp"

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
    links = (_dict(reference).get("link") for reference in _list(references))
    return list(dict.fromkeys(link for link in links if _text(link)))


def _ranked(results):
    return [
        result
        for result in _list(results)
        if isinstance(result, dict) and isinstance(result.get("position"), int)
    ]


def _mention(engine, query, checked_at, found):
    return {
        "_source_id": f"{engine}|{spy.slug(query)}|{checked_at}|{found.company.domain}",
        "_mention_engine": engine,
        "_mention_query": query,
        "_mention_checked_at": checked_at,
        "_company": found.company.name,
        "_role": found.company.role,
        "_rank": found.rank,
    }


def reshape(object_type: str, payload: dict) -> list[dict]:
    engine = ENGINES.get(object_type)
    if engine is None:
        return [payload]
    definition = spy.definition()
    request = _dict(payload.get("request"))
    query = _text(request.get("query"))
    checked_at = _text(request.get("checked_at"))
    check = {
        **payload,
        "_source_id": f"{engine}|{spy.slug(query)}|{checked_at}",
        "_engine": engine,
        "_query": query,
        "_checked_at": checked_at,
    }
    if engine == "google":
        results = _list(_dict(payload.get("response")).get("organic_results"))
        found = spy.serp_mentions(definition, _ranked(results))
        check["_sources"] = len(results)
    else:
        block = _dict(payload.get("ai_overview"))
        answer = "\n".join(_lines({"text_blocks": block.get("text_blocks")}))
        links = _links(block.get("references"))
        found = spy.mentions(definition, answer, links)
        check["_answer"] = answer
        check["_sources"] = len(links)
    brand = next((m.rank for m in found if m.company.role == "brand"), None)
    if brand is not None:
        check["_brand_rank"] = brand
    return [check, *(_mention(engine, query, checked_at, m) for m in found)]
