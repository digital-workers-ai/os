from app.sources.paginators import IntercomCursor
from app.sources.util import client_for, store_all

SOURCE = "intercom"

OBSERVED_AT = {"contacts": "updated_at", "conversations": "updated_at"}

_ENDPOINTS = [
    ("/contacts", "contacts", "data"),
    ("/conversations", "conversations", "conversations"),
]


async def pull(session, store):
    api = client_for(SOURCE)
    notes: dict = {}
    for endpoint, kind, key in _ENDPOINTS:
        records = await api.get(
            endpoint, params={"per_page": 8}, paginate=IntercomCursor(key)
        )
        await store_all(
            session, store, records, source=SOURCE, object_type=kind, notes=notes
        )
    return notes or None
