import json

from app.sources.util import client_for, pick_id, store_all, window

SOURCE = "meta"

OBSERVED_AT = {"campaigns": "updated_time"}

ACCOUNT_CURRENCY = "usd"

ACCOUNT_IDS = ["act_000001", "act_000002", "act_000006", "act_000007"]

POST_FIELDS = (
    "id,message,created_time,type,shares,likes.summary(true),comments.summary(true)"
)
MEDIA_FIELDS = "id,caption,timestamp,media_type,permalink,like_count,comments_count"

PAGE_METRICS = (
    "page_impressions_unique,page_impressions,page_post_engagements,"
    "page_fan_adds,page_fan_removes,page_views_total"
)
IG_METRICS = "reach,impressions,accounts_engaged,follower_count,profile_views"
POST_METRICS = "post_impressions_unique,post_impressions,post_clicks"
MEDIA_METRICS = "reach,impressions,views,saved"


def _daily_id(record):
    if record.get("campaign_id") is None or record.get("date_start") is None:
        return None
    return f"{record['campaign_id']}|{record['date_start']}"


def _report_id(record):
    return f"{record['node']}|{record['date']}"


def _by_day(node, series):
    rows: dict = {}
    for metric in series:
        name = metric.get("name")
        for point in metric.get("values") or []:
            day = str(point.get("end_time") or "")[:10]
            if not name or not day:
                continue
            row = rows.setdefault(day, {"node": node, "date": day, "values": {}})
            row["values"][name] = point.get("value")
    return list(rows.values())


def _lifetime(node, series):
    values = {}
    for metric in series:
        points = metric.get("values") or []
        if metric.get("name") and points:
            values[metric["name"]] = points[0].get("value")
    return {"id": node, "values": values}


async def _daily(
    api, session, store, node, metric, since, until, *, object_type, notes
):
    series = await api.get(
        f"/v25.0/{node}/insights",
        params={"metric": metric, "period": "day", "since": since, "until": until},
        paginate="cursor_meta",
    )
    await store_all(
        session,
        store,
        _by_day(node, series),
        source=SOURCE,
        object_type=object_type,
        id_of=_report_id,
        notes=notes,
    )


async def _lifetimes(api, session, store, records, metric, *, object_type, notes):
    for record in records:
        node = pick_id(record, "id")
        if node is None:
            continue
        series = await api.get(
            f"/v25.0/{node}/insights", params={"metric": metric}, paginate="cursor_meta"
        )
        await store_all(
            session,
            store,
            [_lifetime(node, series)],
            source=SOURCE,
            object_type=object_type,
            notes=notes,
        )


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
            await _daily(
                api,
                session,
                store,
                page_id,
                PAGE_METRICS,
                since,
                until,
                object_type="page_insights",
                notes=notes,
            )
            await _lifetimes(
                api,
                session,
                store,
                posts,
                POST_METRICS,
                object_type="post_insights",
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
            await _daily(
                api,
                session,
                store,
                instagram_id,
                IG_METRICS,
                since,
                until,
                object_type="ig_insights",
                notes=notes,
            )
            await _lifetimes(
                api,
                session,
                store,
                media,
                MEDIA_METRICS,
                object_type="media_insights",
                notes=notes,
            )
    return notes or None
