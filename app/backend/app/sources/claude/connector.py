from app import clock
from app.engine import spy
from app.sources.util import client_for

SOURCE = "claude"
MODEL = "claude-haiku-4-5"
PATH = "/v1/messages"
TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 3}
MAX_TOKENS = 1024

OBSERVED_AT = {"checks": "request.checked_at"}


async def pull(session, store):
    api = client_for(SOURCE)
    checked_at = clock.now().date().isoformat()
    for query in spy.definition().queries:
        data = await api.post(
            PATH,
            json={
                "model": MODEL,
                "max_tokens": MAX_TOKENS,
                "messages": [{"role": "user", "content": query}],
                "tools": [TOOL],
            },
        )
        await store(
            session,
            source=SOURCE,
            object_type="checks",
            source_id=f"{spy.slug(query)}|{checked_at}",
            raw_payload={
                "request": {
                    "engine": SOURCE,
                    "query": query,
                    "checked_at": checked_at,
                    "model": MODEL,
                },
                "response": data,
            },
        )
