from app import clock
from app.engine import spy
from app.sources.util import client_for

SOURCE = "perplexity"
MODEL = "perplexity/sonar"
PATH = "/api/v1/chat/completions"

OBSERVED_AT = {"checks": "request.checked_at"}


async def pull(session, store):
    api = client_for(SOURCE)
    checked_at = clock.now().date().isoformat()
    for query in spy.definition().queries:
        data = await api.post(
            PATH,
            json={"model": MODEL, "messages": [{"role": "user", "content": query}]},
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
