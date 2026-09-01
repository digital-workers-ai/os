from app.sources.util import client_for, declare_page_complete, store_all

SOURCE = "smartlook"

OBSERVED_AT = {}


async def pull(session, store):
    api = client_for(SOURCE)
    data = await api.get("/api/v1/events", params={"limit": 100})
    if isinstance(data, list):
        events = data
    elif isinstance(data, dict):
        events = data.get("data", data.get("events", []))
    else:
        events = []
    if not isinstance(events, list):
        events = []
    declare_page_complete(api, events, 100, "events")
    return (
        await store_all(
            session,
            store,
            events,
            source=SOURCE,
            object_type="events",
            id_fields=("id", "eventId"),
        )
        or None
    )
