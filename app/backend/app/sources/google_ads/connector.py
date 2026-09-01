from app.sources.util import client_for, store_all

SOURCE = "google_ads"

OBSERVED_AT: dict = {}

ACCOUNT_CURRENCY = "usd"

_QUERY = (
    "SELECT campaign.id, campaign.name, campaign.status, metrics.clicks, "
    "metrics.impressions, metrics.costMicros, metrics.conversions "
    "FROM campaign WHERE segments.date DURING LAST_30_DAYS"
)


def _results(data):
    if isinstance(data, list) and data:
        return data[0]["results"]
    if isinstance(data, dict):
        return data.get("results", [])
    return []


async def pull(session, store):
    api = client_for(SOURCE)
    data = await api.post(
        "/v24/customers/1234567890/googleAds:searchStream", json={"query": _QUERY}
    )
    return (
        await store_all(
            session,
            store,
            _results(data),
            source=SOURCE,
            object_type="campaigns",
            id_of=lambda r: (r.get("campaign") or {}).get("id"),
        )
        or None
    )
