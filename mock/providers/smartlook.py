"""
Smartlook API v1 mock provider.
Contract: seeds/docs/11-smartlook.md

Bearer auth. Cursor pagination on sessions/search.
"""

from fastapi import APIRouter, Request, Query, HTTPException
from pydantic import BaseModel
from seeds.helpers import require_bearer, cursor_paginate

router = APIRouter()

_EVENTS = [
    {"id": "evt_click_signup", "name": "click_signup_button", "type": "custom", "created_at": "2026-01-15T10:00:00Z"},
    {"id": "evt_page_pricing", "name": "visit_pricing_page", "type": "custom", "created_at": "2026-02-01T14:30:00Z"},
    {"id": "evt_form_submit", "name": "form_submission", "type": "custom", "created_at": "2026-03-10T09:15:00Z"},
    {"id": "evt_rage_click", "name": "rage_click", "type": "system", "created_at": "2025-12-01T00:00:00Z"},
]

_EVENTS_BY_ID = {e["id"]: e for e in _EVENTS}

_SESSIONS = [
    {
        "id": "sess_abc123",
        "visitorId": "vis_xyz789",
        "duration": 185,
        "startedAt": "2026-06-15T14:32:10.000Z",
        "endedAt": "2026-06-15T14:35:15.000Z",
        "landingPage": "https://acme.io/pricing",
        "exitPage": "https://acme.io/signup",
        "referrer": "https://www.google.com/",
        "identification": {
            "browser": {"name": "Chrome", "version": "126.0"},
            "platform": {"name": "macOS", "version": "15.1"},
            "country": {"city": "San Francisco", "region": "California", "code": "US"},
            "device": {"type": "desktop"},
        },
        "pageUrl": ["https://acme.io/pricing", "https://acme.io/features", "https://acme.io/signup"],
        "eventsCount": 12,
        "dashboardURL": "https://app.smartlook.com/recordings/sess_abc123",
    },
    {
        "id": "sess_def456",
        "visitorId": "vis_uvw321",
        "duration": 42,
        "startedAt": "2026-06-15T15:10:00.000Z",
        "endedAt": "2026-06-15T15:10:42.000Z",
        "landingPage": "https://acme.io/",
        "exitPage": "https://acme.io/",
        "referrer": "",
        "identification": {
            "browser": {"name": "Safari", "version": "18.0"},
            "platform": {"name": "iOS", "version": "19.0"},
            "country": {"city": "London", "region": "England", "code": "GB"},
            "device": {"type": "mobile"},
        },
        "pageUrl": ["https://acme.io/"],
        "eventsCount": 3,
        "dashboardURL": "https://app.smartlook.com/recordings/sess_def456",
    },
    {
        "id": "sess_ghi789",
        "visitorId": "vis_rst654",
        "duration": 320,
        "startedAt": "2026-06-16T09:00:00.000Z",
        "endedAt": "2026-06-16T09:05:20.000Z",
        "landingPage": "https://acme.io/blog/ai-2026",
        "exitPage": "https://acme.io/signup",
        "referrer": "https://twitter.com/",
        "identification": {
            "browser": {"name": "Firefox", "version": "128.0"},
            "platform": {"name": "Windows", "version": "11"},
            "country": {"city": "Austin", "region": "Texas", "code": "US"},
            "device": {"type": "desktop"},
        },
        "pageUrl": ["https://acme.io/blog/ai-2026", "https://acme.io/pricing", "https://acme.io/signup"],
        "eventsCount": 8,
        "dashboardURL": "https://app.smartlook.com/recordings/sess_ghi789",
    },
]

_VISITOR_EVENTS = {
    "vis_xyz789": [
        {"type": "page_visit", "url": "https://acme.io/pricing", "timestamp": 1718458330000, "duration": 45000},
        {"type": "custom", "name": "visit_pricing_page", "timestamp": 1718458330500, "data": {}},
        {"type": "click", "selector": "button.cta-primary", "text": "Start Free Trial", "timestamp": 1718458375000},
        {"type": "page_visit", "url": "https://acme.io/features", "timestamp": 1718458376000, "duration": 60000},
        {"type": "custom", "name": "click_signup_button", "timestamp": 1718458436000, "data": {"plan": "growth"}},
        {"type": "page_visit", "url": "https://acme.io/signup", "timestamp": 1718458437000, "duration": 80000},
    ],
}


class SessionFilter(BaseModel):
    name: str
    operator: str
    value: str | int | list | None = None


class SessionSearchRequest(BaseModel):
    filters: list[SessionFilter] = []


@router.get("/api/v1/events")
async def list_events(
    request: Request,
    limit: int = Query(50),
    after: str = Query(None),
    before: str = Query(None),
    categoryId: str = Query(None),
):
    require_bearer(request)
    return {"events": _EVENTS}


@router.get("/api/v1/events/{event_id}")
async def get_event(
    request: Request,
    event_id: str,
    dateFrom: str = Query(None),
    dateTo: str = Query(None),
    occurrenceHistogramInterval: str = Query(None),
):
    require_bearer(request)

    evt = _EVENTS_BY_ID.get(event_id)
    if not evt:
        raise HTTPException(status_code=404, detail={"error": "Not Found", "message": "Event not found"})

    return {
        "id": evt["id"],
        "name": evt["name"],
        "type": evt["type"],
        "histogram": {
            "labels": ["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04", "2026-06-05"],
            "data": [45, 52, 38, 61, 55],
        },
        "total_count": 251,
        "unique_visitors": 198,
    }


@router.post("/api/v1/sessions/search")
async def search_sessions(
    request: Request,
    body: SessionSearchRequest,
    limit: int = Query(50),
    after: str = Query(None),
):
    require_bearer(request)

    page, next_cursor = cursor_paginate(_SESSIONS, after, limit)

    return {
        "sessions": page,
        "pagination": {"after": next_cursor},
    }


@router.get("/api/v1/visitors/{visitor_id}/events")
async def visitor_events(
    request: Request,
    visitor_id: str,
    sessionId: str = Query(None),
):
    require_bearer(request)
    events = _VISITOR_EVENTS.get(visitor_id, [])
    return {"events": events}
