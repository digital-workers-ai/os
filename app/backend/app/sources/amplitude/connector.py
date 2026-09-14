from app.sources.util import client_for, pick_id, store_ndjson, window

SOURCE = "amplitude"

OBSERVED_AT = {"events": "event_time"}


def _at_hour(day: str, hour: str) -> str:
    return f"{day.replace('-', '')}T{hour}"


async def pull(session, store):
    api = client_for(SOURCE)
    since, until = window()
    text = await api.get_archive(
        "/api/2/export",
        params={"start": _at_hour(since, "00"), "end": _at_hour(until, "23")},
    )
    return await store_ndjson(
        session,
        store,
        text,
        source=SOURCE,
        id_of=lambda e: pick_id(e, "$insert_id", "uuid"),
    )
