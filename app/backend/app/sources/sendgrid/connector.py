from app.sources.util import client_for, store_all

SOURCE = "sendgrid"

OBSERVED_AT = {"contacts": "updated_at", "singlesends": "updated_at"}


async def pull(session, store):
    api = client_for(SOURCE)
    notes: dict = {}
    for endpoint in ("/v3/marketing/singlesends", "/v3/marketing/contacts"):
        kind = endpoint.rsplit("/", 1)[-1]
        data = await api.get(endpoint)
        items = data.get("result", data.get("results"))
        if isinstance(items, list):
            await store_all(
                session, store, items, source=SOURCE, object_type=kind, notes=notes
            )
        else:
            await store(
                session,
                source=SOURCE,
                object_type=kind,
                source_id=kind,
                raw_payload=data,
            )
    return notes or None
