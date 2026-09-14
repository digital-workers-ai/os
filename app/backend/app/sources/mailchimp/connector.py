from app.sources.paginators import Offset
from app.sources.util import client_for, store_all

SOURCE = "mailchimp"

PAGE_SIZE = 1000

OBSERVED_AT: dict = {}


async def pull(session, store):
    api = client_for(SOURCE)
    notes: dict = {}
    for endpoint, kind in [("/3.0/lists", "lists"), ("/3.0/campaigns", "campaigns")]:
        records = await api.get(
            endpoint, params={"count": PAGE_SIZE, "offset": 0}, paginate=Offset(kind)
        )
        await store_all(
            session, store, records, source=SOURCE, object_type=kind, notes=notes
        )
    return notes or None
