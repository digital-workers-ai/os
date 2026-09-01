from app.sources.util import client_for, pick_id, store_all

SOURCE = "calendly"

OBSERVED_AT = {"scheduled_events": "updated_at"}


def _event_id(event):
    return (pick_id(event, "uri") or "").rsplit("/", 1)[-1] or None


async def pull(session, store):
    api = client_for(SOURCE)
    events = await api.get(
        "/scheduled_events", params={"count": 2}, paginate="token_calendly"
    )
    return (
        await store_all(
            session,
            store,
            events,
            source=SOURCE,
            object_type="scheduled_events",
            id_of=_event_id,
        )
        or None
    )
