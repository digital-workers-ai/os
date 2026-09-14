from app.sources.util import client_for, store_all

SOURCE = "hubspot"

OBSERVED_AT = {
    "companies": "properties.hs_lastmodifieddate",
    "contacts": "properties.lastmodifieddate",
    "deals": "properties.hs_lastmodifieddate",
}

PAGE_SIZE = 100

PROPERTIES = {
    "contacts": ("email", "firstname", "lastname", "lastmodifieddate"),
    "companies": ("domain", "industry", "name", "hs_lastmodifieddate"),
    "deals": (
        "dealname",
        "amount",
        "closedate",
        "deal_currency_code",
        "hs_is_closed",
        "hs_is_closed_won",
        "hs_lastmodifieddate",
    ),
}


async def pull(session, store):
    api = client_for(SOURCE)
    notes: dict = {}
    for obj in ("contacts", "companies", "deals"):
        records = await api.get(
            f"/crm/v3/objects/{obj}",
            params={"limit": PAGE_SIZE, "properties": ",".join(PROPERTIES[obj])},
            paginate="cursor_hubspot",
        )
        await store_all(
            session, store, records, source=SOURCE, object_type=obj, notes=notes
        )
    return notes or None
