from app.sources.util import client_for, store_all

SOURCE = "klaviyo"

PROFILES_PAGE_SIZE = 100

FLOWS_PAGE_SIZE = 50

OBSERVED_AT = {"profiles": "attributes.updated", "flows": "attributes.updated"}

ENDPOINTS = (
    ("/api/profiles", PROFILES_PAGE_SIZE),
    ("/api/flows", FLOWS_PAGE_SIZE),
)


async def pull(session, store):
    api = client_for(SOURCE)
    notes: dict = {}
    for endpoint, page_size in ENDPOINTS:
        kind = endpoint.rsplit("/", 1)[-1]
        records = await api.get(
            endpoint, params={"page[size]": page_size}, paginate="cursor_klaviyo"
        )
        await store_all(
            session, store, records, source=SOURCE, object_type=kind, notes=notes
        )
    return notes or None
