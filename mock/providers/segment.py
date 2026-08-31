"""
Segment Public API mock provider.
Contract: seeds/docs/26-segment.md

Bearer auth. Cursor pagination (pagination.cursor). All responses wrapped in data.
"""

from fastapi import APIRouter, Request, Query
from seeds.helpers import require_bearer, token_paginate
from seeds.world import PEOPLE, COMPANIES_BY_ID, SUBSCRIPTIONS_BY_COMPANY

router = APIRouter()


def _seg_profile(p):
    co = COMPANIES_BY_ID.get(p.company_id)
    sub = SUBSCRIPTIONS_BY_COMPANY.get(co.id) if co else None
    return {
        "segmentId": f"seg_user_{p.id}",
        "traits": {
            "email": p.email,
            "first_name": p.first_name, "last_name": p.last_name,
            "company": co.name if co else "",
            "plan": sub.plan if sub else "free",
            "created_at": f"{p.created_at}T00:00:00.000Z",
            "last_seen_at": f"{p.last_seen}T00:00:00.000Z" if p.last_seen else None,
        },
        "external_ids": [
            {"id": f"user_{p.first_name.lower()}_{co.domain.split('.')[0]}" if co else f"user_{p.id}", "type": "user_id", "collection": "users", "created_at": f"{p.created_at}T00:00:00.000Z", "encoding": "none"},
            {"id": p.email, "type": "email", "collection": "users", "created_at": f"{p.created_at}T00:00:00.000Z", "encoding": "none"},
        ],
        "metadata": {
            "createdAt": f"{p.created_at}T00:00:00.000Z",
            "updatedAt": f"{p.last_seen}T00:00:00.000Z" if p.last_seen else f"{p.created_at}T00:00:00.000Z",
        },
    }


_SOURCES = [
    {
        "id": "src_abc123", "slug": "javascript", "name": "Production Website",
        "workspaceId": "ws_mock_001", "enabled": True,
        "writeKeys": ["wk_mock_xxxxxxxxxxxx"],
        "metadata": {"id": "javascript", "name": "Javascript", "slug": "javascript", "description": "Track events from your website", "categories": ["Website"], "isCloudEventSource": False},
        "settings": {}, "labels": [{"key": "environment", "value": "production"}],
        "createdAt": "2025-01-15T10:00:00.000Z", "updatedAt": "2026-06-01T14:00:00.000Z",
    },
    {
        "id": "src_def456", "slug": "python", "name": "Backend Service",
        "workspaceId": "ws_mock_001", "enabled": True,
        "writeKeys": ["wk_mock_yyyyyyyyyyyy"],
        "metadata": {"id": "python", "name": "Python", "slug": "python", "description": "Track events from your Python server", "categories": ["Server"], "isCloudEventSource": False},
        "settings": {}, "labels": [{"key": "environment", "value": "production"}],
        "createdAt": "2025-03-20T08:30:00.000Z", "updatedAt": "2026-05-15T11:00:00.000Z",
    },
    {
        "id": "src_ghi789", "slug": "ios", "name": "iOS App",
        "workspaceId": "ws_mock_001", "enabled": True,
        "writeKeys": ["wk_mock_zzzzzzzzzzzz"],
        "metadata": {"id": "ios", "name": "iOS", "slug": "ios", "description": "Track events from your iOS app", "categories": ["Mobile"], "isCloudEventSource": False},
        "settings": {}, "labels": [{"key": "environment", "value": "production"}],
        "createdAt": "2025-06-01T12:00:00.000Z", "updatedAt": "2026-07-01T09:00:00.000Z",
    },
]

_DESTINATIONS = [
    {
        "id": "dst_abc123", "name": "HubSpot Production", "enabled": True,
        "sourceId": "src_abc123",
        "metadata": {"id": "hubspot", "name": "HubSpot", "slug": "hubspot", "description": "Send data to HubSpot CRM", "categories": ["CRM"], "status": "PUBLIC"},
        "settings": {"apiKey": "****"}, "createdAt": "2025-02-01T12:00:00.000Z", "updatedAt": "2026-06-01T14:00:00.000Z",
    },
    {
        "id": "dst_def456", "name": "Stripe Events", "enabled": True,
        "sourceId": "src_def456",
        "metadata": {"id": "stripe", "name": "Stripe", "slug": "stripe", "description": "Send data to Stripe", "categories": ["Payments"], "status": "PUBLIC"},
        "settings": {"apiKey": "****"}, "createdAt": "2025-02-15T09:00:00.000Z", "updatedAt": "2026-06-01T14:00:00.000Z",
    },
    {
        "id": "dst_ghi789", "name": "Mixpanel Analytics", "enabled": True,
        "sourceId": "src_abc123",
        "metadata": {"id": "mixpanel", "name": "Mixpanel", "slug": "mixpanel", "description": "Send data to Mixpanel", "categories": ["Analytics"], "status": "PUBLIC"},
        "settings": {"apiKey": "****"}, "createdAt": "2025-04-01T10:00:00.000Z", "updatedAt": "2026-05-15T11:00:00.000Z",
    },
]


def _seg_paginate(items, cursor, count):
    page, next_token = token_paginate(items, cursor, count)
    pagination = {
        "current": cursor or "cursor_page1",
        "next": next_token,
        "totalEntries": len(items),
    }
    return page, pagination


@router.get("/sources")
async def list_sources(request: Request, pagination_cursor: str = Query(None, alias="pagination.cursor"), pagination_count: int = Query(200, alias="pagination.count")):
    require_bearer(request)
    page, pagination = _seg_paginate(_SOURCES, pagination_cursor, pagination_count)
    return {"data": {"sources": page, "pagination": pagination}}


@router.get("/destinations")
async def list_destinations(request: Request, pagination_cursor: str = Query(None, alias="pagination.cursor"), pagination_count: int = Query(200, alias="pagination.count")):
    require_bearer(request)
    page, pagination = _seg_paginate(_DESTINATIONS, pagination_cursor, pagination_count)
    return {"data": {"destinations": page, "pagination": pagination}}


@router.get("/spaces/{space_id}/collections/{collection_id}/profiles")
async def list_profiles(
    request: Request,
    space_id: str, collection_id: str,
    pagination_cursor: str = Query(None, alias="pagination.cursor"),
    pagination_count: int = Query(200, alias="pagination.count"),
    include: str = Query(None),
):
    require_bearer(request)
    profiles = [_seg_profile(p) for p in PEOPLE]
    page, pagination = _seg_paginate(profiles, pagination_cursor, pagination_count)
    return {"data": {"profiles": page, "pagination": pagination}}


@router.get("/tracking-plans")
async def list_tracking_plans(request: Request, pagination_cursor: str = Query(None, alias="pagination.cursor"), pagination_count: int = Query(200, alias="pagination.count")):
    require_bearer(request)
    plans = [
        {
            "id": "tp_abc123", "name": "Production Tracking Plan",
            "slug": "production-tracking-plan",
            "description": "Events and properties for our production app",
            "type": "LIVE",
            "createdAt": "2025-01-10T09:00:00.000Z", "updatedAt": "2026-07-01T12:00:00.000Z",
        },
    ]
    return {"data": {"trackingPlans": plans, "pagination": {"current": "cursor_page1", "totalEntries": len(plans)}}}
