from app.sources.paginators import ShopifyLink
from app.sources.util import client_for, store_all

SOURCE = "shopify"

OBSERVED_AT = {
    "customers": "updated_at",
    "orders": "updated_at",
    "products": "updated_at",
}

PROTECTED_CUSTOMER_FIELDS = ("email", "first_name", "last_name", "phone")

PAGE_SIZE = 250


async def pull(session, store):
    api = client_for(SOURCE)
    notes: dict = {}
    for kind in ("products", "orders", "customers"):
        params = {"limit": PAGE_SIZE}
        if kind == "orders":
            params["status"] = "any"
        items = await api.get(
            f"/admin/api/2024-01/{kind}.json",
            params=params,
            paginate=ShopifyLink(kind),
        )
        if kind == "customers":
            withheld = sum(
                1
                for item in items
                if not any(item.get(f) for f in PROTECTED_CUSTOMER_FIELDS)
            )
            if withheld:
                notes["customers_without_personal_data"] = withheld
        await store_all(
            session, store, items, source=SOURCE, object_type=kind, notes=notes
        )
    return notes or None
