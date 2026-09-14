from app.sources.util import client_for, store_ndjson, window

SOURCE = "mixpanel"

OBSERVED_AT = {"events": "properties.time"}

ENDED_EARLY = "terminated early"


async def pull(session, store):
    api = client_for(SOURCE)
    since, until = window()
    text = await api.get_text(
        "/api/2.0/export",
        params={"from_date": since, "to_date": until},
    )
    lines = text.strip().split("\n")
    if lines[-1].strip() == ENDED_EARLY:
        api.truncate("mixpanel ended the export early; the tail was not read")
        text = "\n".join(lines[:-1])
    return await store_ndjson(
        session,
        store,
        text,
        source=SOURCE,
        id_of=lambda e: (e.get("properties") or {}).get("$insert_id"),
    )
