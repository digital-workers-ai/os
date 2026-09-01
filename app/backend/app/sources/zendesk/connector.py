from app.sources.util import client_for, store_all

SOURCE = "zendesk"

OBSERVED_AT = {
    "organizations": "updated_at",
    "tickets": "updated_at",
    "users": "updated_at",
}


async def pull(session, store):
    api = client_for(SOURCE)
    notes: dict = {}
    for endpoint, kind in [
        ("/tickets.json", "tickets"),
        ("/users.json", "users"),
        ("/organizations.json", "organizations"),
    ]:
        records = await api.get(
            endpoint, params={"page[size]": 6}, paginate="cursor_zendesk"
        )
        await store_all(
            session, store, records, source=SOURCE, object_type=kind, notes=notes
        )
    return notes or None
