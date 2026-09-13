from app.sources.util import client_for, store_all, window

SOURCE = "google_ads"

OBSERVED_AT: dict = {}

ACCOUNT_CURRENCY = "usd"

_QUERY = (
    "SELECT campaign.id, campaign.name, campaign.status, metrics.clicks, "
    "metrics.impressions, metrics.costMicros, metrics.conversions "
    "FROM campaign WHERE segments.date DURING LAST_30_DAYS"
)

_DAILY_QUERY = (
    "SELECT campaign.id, segments.date, metrics.costMicros, metrics.clicks, "
    "metrics.impressions, metrics.conversions, metrics.conversionsValue "
    "FROM campaign WHERE segments.date BETWEEN '{since}' AND '{until}'"
)

_SEARCH = "/v24/customers/1234567890/googleAds:searchStream"


def _results(data):
    if isinstance(data, list) and data:
        return data[0]["results"]
    if isinstance(data, dict):
        return data.get("results", [])
    return []


def _daily_id(record):
    campaign_id = (record.get("campaign") or {}).get("id")
    day = (record.get("segments") or {}).get("date")
    if campaign_id is None or day is None:
        return None
    return f"{campaign_id}|{day}"


async def pull(session, store):
    api = client_for(SOURCE)
    notes: dict = {}
    data = await api.post(_SEARCH, json={"query": _QUERY})
    await store_all(
        session,
        store,
        _results(data),
        source=SOURCE,
        object_type="campaigns",
        id_of=lambda r: (r.get("campaign") or {}).get("id"),
        notes=notes,
    )
    since, until = window()
    daily = await api.post(
        _SEARCH, json={"query": _DAILY_QUERY.format(since=since, until=until)}
    )
    await store_all(
        session,
        store,
        _results(daily),
        source=SOURCE,
        object_type="daily_campaigns",
        id_of=_daily_id,
        notes=notes,
    )
    return notes or None
