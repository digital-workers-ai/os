from app.sources.util import client_for, declare_page_complete, store_all

SOURCE = "woocommerce"

OBSERVED_AT = {"orders": "date_modified"}

ACCOUNT_CURRENCY = "usd"


async def pull(session, store):
    api = client_for(SOURCE)
    notes: dict = {}
    for kind in ("products", "orders", "customers"):
        data = await api.get(f"/{kind}", params={"per_page": 100, "page": 1})
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get(kind, [])
        else:
            items = []
        declare_page_complete(api, items, 100, kind)
        await store_all(
            session, store, items, source=SOURCE, object_type=kind, notes=notes
        )
    return notes or None
