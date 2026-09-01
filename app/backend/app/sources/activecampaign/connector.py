from app.sources.paginators import Offset
from app.sources.util import client_for, store_all

SOURCE = "activecampaign"

OBSERVED_AT = {"contacts": "udate", "campaigns": "mdate"}


async def pull(session, store):
    api = client_for(SOURCE)
    notes: dict = {}
    for endpoint, kind in [
        ("/api/3/contacts", "contacts"),
        ("/api/3/campaigns", "campaigns"),
    ]:
        records = await api.get(
            endpoint,
            params={"limit": 8, "offset": 0},
            paginate=Offset(kind, count_param="limit"),
        )
        await store_all(
            session, store, records, source=SOURCE, object_type=kind, notes=notes
        )
    return notes or None
