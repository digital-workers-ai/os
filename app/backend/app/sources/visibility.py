from app.engine import spy


def distinct(links) -> list:
    return list(
        dict.fromkeys(link for link in links if isinstance(link, str) and link.strip())
    )


def _mention(engine, query, checked_at, found) -> dict:
    return {
        "_source_id": f"{engine}|{spy.slug(query)}|{checked_at}|{found.company.domain}",
        "_mention_engine": engine,
        "_mention_query": query,
        "_mention_checked_at": checked_at,
        "_company": found.company.name,
        "_role": found.company.role,
        "_rank": found.rank,
    }


def check_records(
    engine, query, checked_at, payload, *, text=None, links=(), results=None
) -> list[dict]:
    definition = spy.definition()
    check = {
        **payload,
        "_source_id": f"{engine}|{spy.slug(query)}|{checked_at}",
        "_engine": engine,
        "_query": query,
        "_checked_at": checked_at,
    }
    if text is not None:
        check["_answer"] = text
    if results is not None:
        found = spy.serp_mentions(definition, results)
        check["_sources"] = len(results)
    else:
        links = list(links)
        found = spy.mentions(definition, text or "", links)
        check["_sources"] = len(links)
    brand = next((m.rank for m in found if m.company.role == "brand"), None)
    if brand is not None:
        check["_brand_rank"] = brand
    return [check, *(_mention(engine, query, checked_at, m) for m in found)]
