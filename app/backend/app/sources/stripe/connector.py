from app.sources.util import client_for, store_all

SOURCE = "stripe"

OBSERVED_AT = {"customers": "created", "subscriptions": "created"}


async def pull(session, store):
    api = client_for(SOURCE)
    notes: dict = {}
    for endpoint in ("/v1/customers", "/v1/subscriptions"):
        kind = endpoint.rsplit("/", 1)[-1]
        records = await api.get(endpoint, params={"limit": 6}, paginate="cursor_stripe")
        await store_all(
            session, store, records, source=SOURCE, object_type=kind, notes=notes
        )
    return notes or None
