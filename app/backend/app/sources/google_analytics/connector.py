import json

from app.sources.util import client_for, content_id

SOURCE = "google_analytics"

OBSERVED_AT: dict = {}

REPORT_SCHEMA = {
    "dimensions": ["report_date", "channel"],
    "metrics": ["sessions", "users", "pageviews"],
}

_DIMENSIONS = [{"name": "date"}, {"name": "sessionDefaultChannelGroup"}]
_METRICS = [
    {"name": "sessions"},
    {"name": "activeUsers"},
    {"name": "screenPageViews"},
]

assert len(REPORT_SCHEMA["dimensions"]) == len(_DIMENSIONS)
assert len(REPORT_SCHEMA["metrics"]) == len(_METRICS)


async def pull(session, store):
    api = client_for(SOURCE)
    offset, limit = 0, 3
    while True:
        report = await api.post(
            "/properties/123456789:runReport",
            json={
                "dateRanges": [{"startDate": "2026-07-01", "endDate": "2026-07-15"}],
                "dimensions": _DIMENSIONS,
                "metrics": _METRICS,
                "limit": limit,
                "offset": offset,
            },
        )
        rows = report.get("rows", [])
        for row in rows:
            dims = json.dumps(row.get("dimensionValues", row), sort_keys=True)
            await store(
                session,
                source=SOURCE,
                object_type="report_rows",
                source_id=content_id(dims),
                raw_payload=row,
            )
        offset += len(rows)
        total = report.get("rowCount")
        if not rows or (isinstance(total, int) and offset >= total):
            break
