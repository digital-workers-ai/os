from app import clock
from app.engine import spy
from app.sources.util import client_for

SOURCE = "google_serp"

OBSERVED_AT = {"searches": "request.checked_at", "ai_overviews": "request.checked_at"}

SEARCH = "/search.json"
RESULTS_PER_QUERY = 10


def _request(engine, query, checked_at, spec):
    return {
        "engine": engine,
        "query": query,
        "checked_at": checked_at,
        "country": spec.country,
        "language": spec.language,
    }


def _count(notes, key):
    notes[key] = notes.get(key, 0) + 1


async def _overview(api, block, notes):
    if isinstance(block, dict) and block.get("page_token"):
        followed = await api.get(
            SEARCH,
            params={"engine": "google_ai_overview", "page_token": block["page_token"]},
        )
        block = followed.get("ai_overview")
        _count(notes, "ai_overview_fetched")
    if isinstance(block, dict) and "error" in block:
        _count(notes, "ai_overview_errors")
        return None
    if not isinstance(block, dict) or "text_blocks" not in block:
        _count(notes, "ai_overview_absent")
        return None
    return block


async def pull(session, store):
    api = client_for(SOURCE)
    spec = spy.definition()
    checked_at = clock.now().date().isoformat()
    notes: dict = {}
    for query in spec.queries:
        source_id = f"{spy.slug(query)}|{checked_at}"
        data = await api.get(
            SEARCH,
            params={
                "engine": "google",
                "q": query,
                "gl": spec.country.lower(),
                "hl": spec.language,
                "num": RESULTS_PER_QUERY,
            },
        )
        await store(
            session,
            source=SOURCE,
            object_type="searches",
            source_id=source_id,
            raw_payload={
                "request": _request("google", query, checked_at, spec),
                "response": data,
            },
        )
        block = await _overview(api, data.get("ai_overview"), notes)
        if block is None:
            continue
        await store(
            session,
            source=SOURCE,
            object_type="ai_overviews",
            source_id=source_id,
            raw_payload={
                "request": _request("ai_overview", query, checked_at, spec),
                "ai_overview": block,
            },
        )
    return notes or None
