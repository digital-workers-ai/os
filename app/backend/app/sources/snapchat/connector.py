from app.sources.util import client_for, declare_page_complete, store_all

SOURCE = "snapchat"

OBSERVED_AT = {"organizations": "updated_at"}


async def pull(session, store):
    api = client_for(SOURCE)
    data = await api.get("/v1/me/organizations", params={"limit": 100})
    orgs = data.get("organizations", data) if isinstance(data, dict) else data
    if not isinstance(orgs, list):
        return None
    unwrapped = [o.get("organization", o) if isinstance(o, dict) else o for o in orgs]
    declare_page_complete(api, unwrapped, 100, "organizations")
    return (
        await store_all(
            session, store, unwrapped, source=SOURCE, object_type="organizations"
        )
        or None
    )
