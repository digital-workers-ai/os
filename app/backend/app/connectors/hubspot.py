from app.connectors.util import client_for, store_all

SOURCE = "hubspot"

OBJECT_CLASS = {"contacts": "record", "companies": "record", "deals": "record"}

PROPERTIES = {
    "contacts": ("email", "firstname", "lastname", "lastmodifieddate"),
    "companies": ("domain", "industry", "name", "hs_lastmodifieddate"),
    "deals": ("dealname", "amount", "dealstage", "closedate", "hs_lastmodifieddate"),
}


async def pull(session, store):
    api = client_for(SOURCE)
    notes: dict = {}
    for obj in ("contacts", "companies", "deals"):
        records = await api.get(
            f"/crm/v3/objects/{obj}",
            params={"limit": 8, "properties": ",".join(PROPERTIES[obj])},
            paginate="cursor_hubspot",
        )
        await store_all(
            session, store, records, source=SOURCE, object_type=obj, notes=notes
        )
    return notes or None
