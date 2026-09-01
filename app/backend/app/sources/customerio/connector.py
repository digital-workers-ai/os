from app.sources.util import client_for, store_all

SOURCE = "customerio"

OBSERVED_AT = {"activities": "timestamp"}


async def pull(session, store):
    api = client_for(SOURCE)
    notes: dict = {}
    for endpoint in ("/v1/campaigns", "/v1/segments"):
        kind = endpoint.rsplit("/", 1)[-1]
        records = await api.get(
            endpoint, params={"limit": 5}, paginate="cursor_customerio"
        )
        await store_all(
            session,
            store,
            records,
            source=SOURCE,
            object_type=kind,
            id_fields=("id", "name"),
            notes=notes,
        )
    activities = await api.get(
        "/v1/activities", params={"limit": 100}, paginate="cursor_customerio_activities"
    )
    await store_all(
        session,
        store,
        activities,
        source=SOURCE,
        object_type="activities",
        id_fields=("delivery_id",),
        notes=notes,
    )
    return notes or None
