import json

from app.sources.util import client_for, store_all, window

SOURCE = "meta"

OBSERVED_AT = {"campaigns": "updated_time"}

ACCOUNT_CURRENCY = "usd"

ACCOUNT_IDS = ["act_000001", "act_000002", "act_000006", "act_000007"]

POST_FIELDS = (
    "id,message,created_time,type,shares,likes.summary(true),comments.summary(true)"
)
MEDIA_FIELDS = "id,caption,timestamp,media_type,permalink,like_count,comments_count"


def _daily_id(record):
    if record.get("campaign_id") is None or record.get("date_start") is None:
        return None
    return f"{record['campaign_id']}|{record['date_start']}"


async def pull(session, store):
    api = client_for(SOURCE)
    notes: dict = {}
    since, until = window()
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
        daily = await api.get(
            f"/v25.0/{account_id}/insights",
            params={
                "level": "campaign",
                "time_increment": "1",
                "time_range": json.dumps({"since": since, "until": until}),
            },
            paginate="cursor_meta",
        )
        await store_all(
            session,
            store,
            daily,
            source=SOURCE,
            object_type="daily_insights",
            id_of=_daily_id,
            notes=notes,
        )
    for page in await api.get("/v25.0/me/accounts", paginate="cursor_meta"):
        page_id = page.get("id")
        if page_id:
            posts = await api.get(
                f"/v25.0/{page_id}/posts",
                params={"since": since, "until": until, "fields": POST_FIELDS},
                paginate="cursor_meta",
            )
            await store_all(
                session,
                store,
                posts,
                source=SOURCE,
                object_type="page_posts",
                notes=notes,
            )
        instagram_id = (page.get("instagram_business_account") or {}).get("id")
        if instagram_id:
            media = await api.get(
                f"/v25.0/{instagram_id}/media",
                params={"since": since, "until": until, "fields": MEDIA_FIELDS},
                paginate="cursor_meta",
            )
            await store_all(
                session,
                store,
                media,
                source=SOURCE,
                object_type="ig_media",
                notes=notes,
            )
    return notes or None
