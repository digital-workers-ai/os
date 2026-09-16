from app import clock
from app.engine import spy
from app.sources.util import client_for

SOURCE = "chatgpt"
MODEL = "openai/gpt-5.6-luna"
PATH = "/api/v1/chat/completions"
OBSERVED_AT = {"checks": "request.checked_at"}
WEB_PLUGIN = {"id": "web", "engine": "native", "max_results": 5}


async def pull(session, store):
    api = client_for(SOURCE)
    spec = spy.definition()
    checked_at = clock.now().date().isoformat()
    for query in spec.queries:
        data = await api.post(
            PATH,
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": query}],
                "plugins": [WEB_PLUGIN],
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
