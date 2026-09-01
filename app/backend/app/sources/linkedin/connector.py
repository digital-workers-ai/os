from app.sources.util import client_for, store_all

SOURCE = "linkedin"

OBSERVED_AT = {"ad_accounts": "lastModified"}


async def pull(session, store):
    api = client_for(SOURCE)
    elements = await api.get(
        "/adAccounts",
        params={"q": "search", "pageSize": 1},
        paginate="token_linkedin",
    )
    return (
        await store_all(
            session, store, elements, source=SOURCE, object_type="ad_accounts"
        )
        or None
    )
