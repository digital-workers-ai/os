from app.sources.util import client_for, store_ndjson

SOURCE = "amplitude"

OBSERVED_AT = {"events": "event_time"}


async def pull(session, store):
    api = client_for(SOURCE)
    text = await api.get_text(
        "/api/2/export", params={"start": "20260701T00", "end": "20260715T00"}
    )
    return await store_ndjson(
        session,
        store,
        text,
        source=SOURCE,
        id_of=lambda e: e.get("insert_id") or e.get("uuid"),
    )
