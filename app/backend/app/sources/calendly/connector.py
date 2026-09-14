from app.sources.client import ConnectorError
from app.sources.util import client_for, pick_id, store_all

SOURCE = "calendly"

PAGE_SIZE = 100

OBSERVED_AT = {"scheduled_events": "updated_at"}


def _event_id(event):
    return (pick_id(event, "uri") or "").rsplit("/", 1)[-1] or None


async def _user_uri(api):
    configured = api.default_params.get("user")
    if configured:
        return configured
    me = await api.get("/users/me")
    return (me.get("resource") or {}).get("uri")


async def pull(session, store):
    api = client_for(SOURCE)
    events = await api.get(
        "/scheduled_events",
        params={"user": await _user_uri(api), "count": PAGE_SIZE},
        paginate="token_calendly",
    )
    notes: dict = {}
    records = []
    for event in events:
        record = dict(event)
        uuid = _event_id(event)
        if uuid:
            try:
                record["_invitees"] = await api.get(
                    f"/scheduled_events/{uuid}/invitees",
                    params={"count": PAGE_SIZE},
                    paginate="token_calendly",
                )
            except ConnectorError:
                notes["invitees_fetch_failed"] = (
                    notes.get("invitees_fetch_failed", 0) + 1
                )
        records.append(record)
    return (
        await store_all(
            session,
            store,
            records,
            source=SOURCE,
            object_type="scheduled_events",
            id_of=_event_id,
            notes=notes,
        )
        or None
    )
