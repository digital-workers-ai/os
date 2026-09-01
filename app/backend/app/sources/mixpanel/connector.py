from app.sources.util import client_for, store_ndjson

SOURCE = "mixpanel"

OBSERVED_AT = {"events": "properties.time"}


async def pull(session, store):
    api = client_for(SOURCE)
    text = await api.get_text(
        "/api/2.0/export",
        params={"from_date": "2026-07-01", "to_date": "2026-07-15"},
    )
    return await store_ndjson(
        session,
        store,
        text,
        source=SOURCE,
        id_of=lambda e: (e.get("properties") or {}).get("$insert_id"),
    )
