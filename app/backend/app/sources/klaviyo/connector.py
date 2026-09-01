from app.sources.util import client_for, store_all

SOURCE = "klaviyo"

OBSERVED_AT = {"profiles": "attributes.updated", "flows": "attributes.updated"}


async def pull(session, store):
    api = client_for(SOURCE)
    notes: dict = {}
    for endpoint in ("/api/profiles", "/api/flows"):
        kind = endpoint.rsplit("/", 1)[-1]
        records = await api.get(
            endpoint, params={"page[size]": 8}, paginate="cursor_klaviyo"
        )
        await store_all(
            session, store, records, source=SOURCE, object_type=kind, notes=notes
        )
    return notes or None
