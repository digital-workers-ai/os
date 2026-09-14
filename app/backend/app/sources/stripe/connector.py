from app.sources.util import client_for, store_all

SOURCE = "stripe"

API_VERSION = "2025-03-31.basil"

PAGE_SIZE = 100

OBSERVED_AT = {"customers": "created", "subscriptions": "created"}

ENDPOINTS = (
    ("/v1/customers", {}),
    ("/v1/subscriptions", {"status": "all"}),
)


async def pull(session, store):
    api = client_for(SOURCE)
    api.headers = {**api.headers, "Stripe-Version": API_VERSION}
    notes: dict = {}
    for endpoint, filters in ENDPOINTS:
        kind = endpoint.rsplit("/", 1)[-1]
        records = await api.get(
            endpoint, params={"limit": PAGE_SIZE, **filters}, paginate="cursor_stripe"
        )
        await store_all(
            session, store, records, source=SOURCE, object_type=kind, notes=notes
        )
    return notes or None
