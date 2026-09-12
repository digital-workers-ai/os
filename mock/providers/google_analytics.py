"""
Google Analytics 4 (GA4) Data API mock provider.
Contract: seeds/docs/08-google-analytics.md

Single POST runReport endpoint. Offset pagination via request body.
"""

from datetime import date

from fastapi import APIRouter, Request
from pydantic import BaseModel
from seeds.helpers import require_bearer, day_factor, days_between

router = APIRouter()


class DateRange(BaseModel):
    startDate: str
    endDate: str


class DimOrMetric(BaseModel):
    name: str


class RunReportRequest(BaseModel):
    dateRanges: list[DateRange] = []
    dimensions: list[DimOrMetric] = []
    metrics: list[DimOrMetric] = []
    limit: int = 10000
    offset: int = 0
    cohortSpec: dict | None = None


_CHANNEL_DATA = [
    ("Organic Search", "1250", "430", "980", "3200", "0.6432", "185.4"),
    ("Direct", "820", "210", "650", "1800", "0.5891", "142.7"),
    ("Paid Search", "540", "380", "420", "1100", "0.5120", "98.3"),
    ("Social", "310", "180", "250", "680", "0.4890", "76.2"),
    ("Referral", "190", "95", "160", "420", "0.5530", "120.1"),
    ("Email", "280", "45", "240", "750", "0.6200", "155.8"),
]

_LANDING_PAGES = [
    ("/", "2100", "12", "0.5830"),
    ("/pricing", "890", "45", "0.7120"),
    ("/features", "650", "8", "0.6210"),
    ("/blog/ai-2026", "420", "3", "0.4890"),
    ("/signup", "310", "89", "0.8900"),
    ("/docs", "280", "2", "0.5540"),
]

_DEVICES = [
    ("desktop", "1890"),
    ("mobile", "1120"),
    ("tablet", "380"),
]

_SOURCES = [
    ("google / organic", "1250", "430", "0.6432", "12"),
    ("(direct) / (none)", "820", "210", "0.5891", "5"),
    ("google / cpc", "540", "380", "0.5120", "45"),
    ("linkedin.com / social", "180", "120", "0.4890", "3"),
    ("newsletter / email", "280", "45", "0.6200", "8"),
]

_GEO = [
    ("San Francisco", "California", "580"),
    ("New York", "New York", "420"),
    ("Austin", "Texas", "310"),
    ("Chicago", "Illinois", "280"),
    ("London", "England", "190"),
]


def _make_row(dim_values, metric_values):
    return {
        "dimensionValues": [{"value": v} for v in dim_values],
        "metricValues": [{"value": v} for v in metric_values],
    }


def _metric_type(name):
    floats = {"engagementRate", "averageSessionDuration", "conversionsValue"}
    if name in floats:
        return "TYPE_FLOAT" if name == "engagementRate" else "TYPE_SECONDS"
    return "TYPE_INTEGER"


@router.post("/properties/{property_id}:runReport")
async def run_report(request: Request, property_id: str, body: RunReportRequest):
    require_bearer(request)

    dim_names = [d.name for d in body.dimensions]
    metric_names = [m.name for m in body.metrics]

    dim_headers = [{"name": n} for n in dim_names]
    metric_headers = [{"name": n, "type": _metric_type(n)} for n in metric_names]

    if body.cohortSpec:
        return _cohort_report(dim_headers, metric_headers, body)

    rows = _generate_rows(dim_names, metric_names, body.dateRanges)

    total = len(rows)
    page = rows[body.offset: body.offset + body.limit]

    return {
        "dimensionHeaders": dim_headers,
        "metricHeaders": metric_headers,
        "rows": page,
        "rowCount": total,
        "kind": "analyticsData#runReport",
        "metadata": {"currencyCode": "USD", "timeZone": "America/Los_Angeles"},
    }


def _report_days(date_ranges):
    if not date_ranges:
        return [date(2026, 7, 1)]
    first = date_ranges[0]
    return days_between(date.fromisoformat(first.startDate), date.fromisoformat(first.endDate))


def _generate_rows(dim_names, metric_names, date_ranges):
    date_str = date_ranges[0].startDate.replace("-", "") if date_ranges else "20260701"

    has_channel = "sessionDefaultChannelGroup" in dim_names
    has_landing = "landingPage" in dim_names
    has_device = "deviceCategory" in dim_names
    has_source = "sessionSourceMedium" in dim_names
    has_geo = "city" in dim_names

    rows = []

    if has_channel:
        all_metrics = ["sessions", "newUsers", "activeUsers", "screenPageViews", "engagementRate", "averageSessionDuration"]
        counted = {"sessions", "newUsers", "activeUsers", "screenPageViews"}
        for day in _report_days(date_ranges):
            factor = day_factor(day)
            for channel_row in _CHANNEL_DATA:
                channel = channel_row[0]
                metric_map = dict(zip(all_metrics, channel_row[1:]))
                for name in counted:
                    metric_map[name] = str(round(int(metric_map[name]) * factor))
                dims = [day.strftime("%Y%m%d"), channel]
                mets = [metric_map.get(m, "0") for m in metric_names]
                rows.append(_make_row(dims, mets))
    elif has_landing:
        all_metrics = ["sessions", "keyEvents", "engagementRate"]
        for lp_row in _LANDING_PAGES:
            page = lp_row[0]
            metric_map = dict(zip(all_metrics, lp_row[1:]))
            dims = [date_str, page]
            mets = [metric_map.get(m, "0") for m in metric_names]
            rows.append(_make_row(dims, mets))
    elif has_device:
        for dev_row in _DEVICES:
            rows.append(_make_row([date_str, dev_row[0]], [dev_row[1]]))
    elif has_source:
        all_metrics = ["sessions", "newUsers", "engagementRate", "keyEvents"]
        for src_row in _SOURCES:
            source = src_row[0]
            metric_map = dict(zip(all_metrics, src_row[1:]))
            dims = [date_str, source]
            mets = [metric_map.get(m, "0") for m in metric_names]
            rows.append(_make_row(dims, mets))
    elif has_geo:
        has_region = "region" in dim_names
        for geo_row in _GEO:
            dims = [date_str, geo_row[0]]
            if has_region:
                dims.append(geo_row[1])
            rows.append(_make_row(dims, [geo_row[2]]))
    else:
        dim_values = []
        for d in dim_names:
            if d == "dateHour":
                dim_values.append(date_str + "14")
            elif d == "dayOfWeek":
                dim_values.append("3")
            elif d == "date":
                dim_values.append(date_str)
            else:
                dim_values.append(date_str)
        rows.append(_make_row(dim_values, ["3390" if i == 0 else "0" for i in range(len(metric_names))]))

    return rows


def _cohort_report(dim_headers, metric_headers, body):
    rows = [
        _make_row(["cohort_week_1", "0000"], ["500", "500"]),
        _make_row(["cohort_week_1", "0001"], ["320", "500"]),
        _make_row(["cohort_week_1", "0002"], ["210", "500"]),
    ]
    return {
        "dimensionHeaders": dim_headers,
        "metricHeaders": metric_headers,
        "rows": rows,
        "rowCount": len(rows),
        "metadata": {"currencyCode": "USD", "timeZone": "America/Los_Angeles"},
    }
