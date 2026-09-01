from app.sources.util import client_for, declare_page_complete, store_all

SOURCE = "twitter"

OBSERVED_AT = {"accounts": "updated_at"}


async def pull(session, store):
    api = client_for(SOURCE)
    data = await api.get("/12/accounts", params={"count": 100})
    accounts = data.get("data", data) if isinstance(data, dict) else data
    if not isinstance(accounts, list):
        return None
    declare_page_complete(api, accounts, 100, "accounts")
    return (
        await store_all(session, store, accounts, source=SOURCE, object_type="accounts")
        or None
    )
