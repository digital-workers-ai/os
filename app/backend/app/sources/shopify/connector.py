from app.sources.paginators import ShopifyLink
from app.sources.util import client_for, store_all

SOURCE = "shopify"

OBSERVED_AT = {
    "customers": "updated_at",
    "orders": "updated_at",
    "products": "updated_at",
}


async def pull(session, store):
    api = client_for(SOURCE)
    notes: dict = {}
    for kind in ("products", "orders", "customers"):
        params = {"limit": 1}
        if kind == "orders":
            params["status"] = "any"
        items = await api.get(
            f"/admin/api/2024-01/{kind}.json",
            params=params,
            paginate=ShopifyLink(kind),
        )
        await store_all(
            session, store, items, source=SOURCE, object_type=kind, notes=notes
        )
    return notes or None
