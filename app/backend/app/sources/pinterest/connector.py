from app.sources.util import client_for, store_all

SOURCE = "pinterest"

OBSERVED_AT = {"ad_accounts": "updated_time"}


async def pull(session, store):
    api = client_for(SOURCE)
    items = await api.get(
        "/ad_accounts", params={"page_size": 1}, paginate="bookmark_pinterest"
    )
    return (
        await store_all(session, store, items, source=SOURCE, object_type="ad_accounts")
        or None
    )
