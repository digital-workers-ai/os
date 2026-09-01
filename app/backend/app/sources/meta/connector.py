from app.sources.util import client_for, store_all

SOURCE = "meta"

OBSERVED_AT = {"campaigns": "updated_time"}

ACCOUNT_CURRENCY = "usd"

ACCOUNT_IDS = ["act_000001", "act_000002", "act_000006", "act_000007"]


async def pull(session, store):
    api = client_for(SOURCE)
    notes: dict = {}
    for account_id in ACCOUNT_IDS:
        campaigns = await api.get(
            f"/v25.0/{account_id}/campaigns",
            params={"limit": 2},
            paginate="cursor_meta",
        )
        await store_all(
            session,
            store,
            campaigns,
            source=SOURCE,
            object_type="campaigns",
            notes=notes,
        )
        insights = await api.get(
            f"/v25.0/{account_id}/insights",
            params={"level": "campaign"},
            paginate="cursor_meta",
        )
        await store_all(
            session,
            store,
            insights,
            source=SOURCE,
            object_type="insights",
            id_fields=("campaign_id", "account_id"),
            notes=notes,
        )
    return notes or None
