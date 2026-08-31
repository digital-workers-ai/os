"""
Klaviyo API mock provider.
Contract: seeds/docs/18-klaviyo.md

Klaviyo-API-Key + revision headers. JSON:API format. Cursor pagination via page[cursor].
"""

from fastapi import APIRouter, Request, Query
from seeds.helpers import require_header, token_paginate
from seeds.world import PEOPLE, COMPANIES_BY_ID, EMAIL_CAMPAIGNS

router = APIRouter()


def _kl_auth(request: Request):
    from fastapi import HTTPException
    api_key = request.headers.get("klaviyo-api-key", "")
    auth = request.headers.get("authorization", "")
    if not api_key and not auth.startswith("Klaviyo-API-Key "):
        raise HTTPException(status_code=401, detail={"errors": [{"status": 401, "code": "not_authenticated", "title": "Not authenticated.", "detail": "Missing or invalid API key."}]})
    require_header(request, "revision")


def _kl_profile(p):
    co = COMPANIES_BY_ID.get(p.company_id)
    return {
        "type": "profile",
        "id": f"kl_prof_{p.id}",
        "attributes": {
            "email": p.email, "phone_number": p.phone,
            "external_id": p.id,
            "first_name": p.first_name, "last_name": p.last_name,
            "organization": co.name if co else None,
            "title": p.role,
            "image": None,
            "location": {"city": co.city if co else None, "region": co.state if co else None, "country": co.country if co else "US", "zip": None},
            "properties": {},
            "created": f"{p.created_at}T00:00:00+00:00",
            "updated": f"{p.last_seen}T00:00:00+00:00" if p.last_seen else f"{p.created_at}T00:00:00+00:00",
            "last_event_date": f"{p.last_seen}T00:00:00+00:00" if p.last_seen else None,
            "subscriptions": {"email": {"marketing": {"consent": "SUBSCRIBED"}}},
            "predictive_analytics": {"historic_clv": 0, "predicted_clv": 0, "total_clv": 0, "historic_number_of_orders": 0, "predicted_number_of_orders": 0, "average_days_between_orders": None, "average_order_value": 0, "churn_probability": 0, "expected_date_of_next_order": None},
        },
        "relationships": {
            "lists": {"links": {"self": f"/api/profiles/kl_prof_{p.id}/relationships/lists", "related": f"/api/profiles/kl_prof_{p.id}/lists"}},
            "segments": {"links": {"self": f"/api/profiles/kl_prof_{p.id}/relationships/segments", "related": f"/api/profiles/kl_prof_{p.id}/segments"}},
        },
        "links": {"self": f"/api/profiles/kl_prof_{p.id}"},
    }


def _kl_campaign(ec):
    return {
        "type": "campaign",
        "id": f"kl_camp_{ec.id}",
        "attributes": {
            "name": ec.name, "status": ec.status.capitalize(),
            "archived": False,
            "channel": "email",
            "message": ec.subject,
            "audiences": {"included": [], "excluded": []},
            "send_strategy": {"method": "immediate"},
            "tracking_options": {"is_tracking_opens": True, "is_tracking_clicks": True},
            "scheduled_at": ec.sent_at,
            "send_time": ec.sent_at,
            "created_at": "2026-06-20T10:00:00+00:00",
            "updated_at": ec.sent_at or "2026-06-20T10:00:00+00:00",
            "send_options": {"use_smart_sending": True},
        },
        "relationships": {
            "campaign-messages": {"links": {"self": f"/api/campaigns/kl_camp_{ec.id}/relationships/campaign-messages", "related": f"/api/campaigns/kl_camp_{ec.id}/campaign-messages"}},
            "tags": {"links": {"self": f"/api/campaigns/kl_camp_{ec.id}/relationships/tags", "related": f"/api/campaigns/kl_camp_{ec.id}/tags"}},
        },
        "links": {"self": f"/api/campaigns/kl_camp_{ec.id}"},
    }


@router.get("/api/profiles")
async def list_profiles(request: Request, page_cursor: str = Query(None, alias="page[cursor]"), page_size: int = Query(20, alias="page[size]")):
    _kl_auth(request)
    profiles = [_kl_profile(p) for p in PEOPLE]
    page, next_token = token_paginate(profiles, page_cursor, page_size)
    return {
        "data": page,
        "links": {
            "self": "/api/profiles",
            "next": f"/api/profiles?page[cursor]={next_token}" if next_token else None,
            "prev": None,
        },
    }


@router.get("/api/flows")
async def list_flows(request: Request, page_cursor: str = Query(None, alias="page[cursor]"), page_size: int = Query(50, alias="page[size]")):
    _kl_auth(request)
    flows = [
        {
            "type": "flow", "id": "kl_flow_001",
            "attributes": {"name": "Welcome Series", "status": "live", "archived": False, "trigger_type": "Added to List", "created": "2025-02-01T10:00:00+00:00", "updated": "2026-06-15T08:00:00+00:00"},
            "relationships": {
                "flow-actions": {"links": {"self": "/api/flows/kl_flow_001/relationships/flow-actions", "related": "/api/flows/kl_flow_001/flow-actions"}},
                "tags": {"links": {"self": "/api/flows/kl_flow_001/relationships/tags", "related": "/api/flows/kl_flow_001/tags"}},
            },
            "links": {"self": "/api/flows/kl_flow_001"},
        },
        {
            "type": "flow", "id": "kl_flow_002",
            "attributes": {"name": "Abandoned Cart", "status": "live", "archived": False, "trigger_type": "Metric", "created": "2025-04-10T14:00:00+00:00", "updated": "2026-07-01T09:00:00+00:00"},
            "relationships": {
                "flow-actions": {"links": {"self": "/api/flows/kl_flow_002/relationships/flow-actions", "related": "/api/flows/kl_flow_002/flow-actions"}},
                "tags": {"links": {"self": "/api/flows/kl_flow_002/relationships/tags", "related": "/api/flows/kl_flow_002/tags"}},
            },
            "links": {"self": "/api/flows/kl_flow_002"},
        },
        {
            "type": "flow", "id": "kl_flow_003",
            "attributes": {"name": "Post-Purchase Follow-up", "status": "live", "archived": False, "trigger_type": "Metric", "created": "2025-06-20T11:00:00+00:00", "updated": "2026-06-28T16:00:00+00:00"},
            "relationships": {
                "flow-actions": {"links": {"self": "/api/flows/kl_flow_003/relationships/flow-actions", "related": "/api/flows/kl_flow_003/flow-actions"}},
                "tags": {"links": {"self": "/api/flows/kl_flow_003/relationships/tags", "related": "/api/flows/kl_flow_003/tags"}},
            },
            "links": {"self": "/api/flows/kl_flow_003"},
        },
    ]
    return {
        "data": flows,
        "links": {"self": "/api/flows", "next": None, "prev": None},
    }


@router.get("/api/campaigns")
async def list_campaigns(request: Request, page_cursor: str = Query(None, alias="page[cursor]"), page_size: int = Query(50, alias="page[size]")):
    _kl_auth(request)
    campaigns = [_kl_campaign(ec) for ec in EMAIL_CAMPAIGNS]
    page, next_token = token_paginate(campaigns, page_cursor, page_size)
    return {
        "data": page,
        "links": {
            "self": "/api/campaigns",
            "next": f"/api/campaigns?page[cursor]={next_token}" if next_token else None,
            "prev": None,
        },
    }


@router.get("/api/metrics")
async def list_metrics(request: Request, page_cursor: str = Query(None, alias="page[cursor]"), page_size: int = Query(50, alias="page[size]")):
    _kl_auth(request)
    metrics = [
        {"type": "metric", "id": "kl_met_001", "attributes": {"name": "Received Email", "created": "2025-01-01T00:00:00+00:00", "updated": "2026-07-01T00:00:00+00:00", "integration": {"object": "integration", "id": "klaviyo", "name": "Klaviyo", "category": "Internal"}}, "links": {"self": "/api/metrics/kl_met_001"}},
        {"type": "metric", "id": "kl_met_002", "attributes": {"name": "Opened Email", "created": "2025-01-01T00:00:00+00:00", "updated": "2026-07-01T00:00:00+00:00", "integration": {"object": "integration", "id": "klaviyo", "name": "Klaviyo", "category": "Internal"}}, "links": {"self": "/api/metrics/kl_met_002"}},
        {"type": "metric", "id": "kl_met_003", "attributes": {"name": "Clicked Email", "created": "2025-01-01T00:00:00+00:00", "updated": "2026-07-01T00:00:00+00:00", "integration": {"object": "integration", "id": "klaviyo", "name": "Klaviyo", "category": "Internal"}}, "links": {"self": "/api/metrics/kl_met_003"}},
        {"type": "metric", "id": "kl_met_004", "attributes": {"name": "Placed Order", "created": "2025-01-01T00:00:00+00:00", "updated": "2026-07-01T00:00:00+00:00", "integration": {"object": "integration", "id": "shopify", "name": "Shopify", "category": "eCommerce"}}, "links": {"self": "/api/metrics/kl_met_004"}},
    ]
    return {
        "data": metrics,
        "links": {"self": "/api/metrics", "next": None, "prev": None},
    }
