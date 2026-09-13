from app.sources.util import client_for, store_all, window

SOURCE = "pinterest"

OBSERVED_AT = {"ad_accounts": "updated_time"}

ACCOUNT = "user_account"

METRIC_TYPES = "IMPRESSION,ENGAGEMENT,TOTAL_AUDIENCE,PIN_CLICK,SAVE"


def _day_id(record):
    day = record.get("date")
    return f"{ACCOUNT}|{day}" if day else None


async def pull(session, store):
    api = client_for(SOURCE)
    notes: dict = {}
    since, until = window()
    items = await api.get(
        "/ad_accounts", params={"page_size": 1}, paginate="bookmark_pinterest"
    )
    await store_all(
        session, store, items, source=SOURCE, object_type="ad_accounts", notes=notes
    )
    pins = await api.get(
        "/pins",
        params={"pin_metrics": "true", "page_size": 100},
        paginate="bookmark_pinterest",
    )
    await store_all(
        session, store, pins, source=SOURCE, object_type="pins", notes=notes
    )
    analytics = await api.get(
        f"/{ACCOUNT}/analytics",
        params={"start_date": since, "end_date": until, "metric_types": METRIC_TYPES},
    )
    days = (
        (analytics.get("all") or {}).get("daily_metrics")
        if isinstance(analytics, dict)
        else None
    )
    await store_all(
        session,
        store,
        days if isinstance(days, list) else [],
        source=SOURCE,
        object_type="account_analytics",
        id_of=_day_id,
        notes=notes,
    )
    return notes or None
