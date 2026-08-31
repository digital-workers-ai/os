"""
Customer.io App API mock provider.
Contract: seeds/docs/03-customerio.md
"""

from fastapi import APIRouter, Request, Query
from seeds.helpers import require_bearer, cursor_paginate
from seeds.world import EMAIL_CAMPAIGNS, PEOPLE, COMPANIES_BY_ID

router = APIRouter()


def _cio_campaign(ec):
    return {
        "id": int(ec.id[2:]) + 100,
        "name": ec.name,
        "type": "triggered",
        "active": ec.status in ("sent", "sending", "scheduled"),
        "created": 1719792000 + int(ec.id[2:]) * 86400,
        "updated": 1720500000,
        "tags": ["email", ec.name.lower().split()[0]],
        "msg_templates_count": 2 + int(ec.id[2:]),
        "actions_count": 3 + int(ec.id[2:]),
    }


def _cio_activity(person, idx):
    types = ["email_sent", "email_opened", "email_clicked"]
    activity_type = types[idx % len(types)]
    data = {"template_id": 201}
    if activity_type == "email_sent":
        data["subject"] = "Welcome to the platform!"
    elif activity_type == "email_clicked":
        data["link_url"] = "https://app.example.com/getting-started"

    return {
        "type": activity_type,
        "delivery_id": f"del_{idx:03d}",
        "timestamp": 1720500000 + idx * 3600,
        "customer_id": person.email,
        "campaign_name": "Welcome Series",
        "campaign_id": 101,
        "data": data,
    }


def _cio_campaign_metrics(ec):
    return {
        "metric": {
            "series": {
                "sent": [ec.sends],
                "delivered": [ec.sends - ec.bounces],
                "opened": [ec.opens],
                "clicked": [ec.clicks],
                "bounced": [ec.bounces],
                "unsubscribed": [ec.unsubscribes],
                "spammed": [0],
                "converted": [max(1, ec.clicks // 3)],
                "dropped": [0],
            },
            "start": "2026-04-01 00:00:00 +0000 UTC",
            "end": "2026-07-01 00:00:00 +0000 UTC",
        }
    }


# --- Endpoints ---

@router.get("/v1/campaigns")
async def list_campaigns(
    request: Request,
    limit: int = Query(100, ge=1, le=1000),
    cursor: str = Query(None),
):
    require_bearer(request)
    all_campaigns = [_cio_campaign(ec) for ec in EMAIL_CAMPAIGNS]
    page, next_cursor = cursor_paginate(all_campaigns, cursor, limit)

    result = {"campaigns": page}
    if next_cursor:
        result["next_cursor"] = next_cursor
    return result


@router.get("/v1/campaigns/{campaign_id}/metrics")
async def campaign_metrics(
    request: Request,
    campaign_id: int,
    period: str = Query("days"),
    steps: int = Query(1),
    start: int = Query(None),
    end: int = Query(None),
):
    require_bearer(request)
    idx = campaign_id - 101
    if 0 <= idx < len(EMAIL_CAMPAIGNS):
        return _cio_campaign_metrics(EMAIL_CAMPAIGNS[idx])
    return {"metric": {"series": {"sent": [0], "delivered": [0], "opened": [0], "clicked": [0], "bounced": [0], "unsubscribed": [0], "spammed": [0], "converted": [0], "dropped": [0]}, "start": "2026-04-01 00:00:00 +0000 UTC", "end": "2026-07-01 00:00:00 +0000 UTC"}}


@router.get("/v1/campaigns/{campaign_id}/metrics/links")
async def campaign_link_metrics(
    request: Request,
    campaign_id: int,
    period: str = Query("days"),
    steps: int = Query(1),
    unique: bool = Query(False),
):
    require_bearer(request)
    idx = campaign_id - 101
    clicks = EMAIL_CAMPAIGNS[idx].clicks if 0 <= idx < len(EMAIL_CAMPAIGNS) else 0
    return {
        "links": [
            {"link": "https://app.example.com/getting-started", "clicks": clicks, "unique_clicks": int(clicks * 0.8)},
            {"link": "https://app.example.com/docs", "clicks": max(1, clicks // 2), "unique_clicks": max(1, int(clicks * 0.4))},
        ]
    }


@router.get("/v1/activities")
async def list_activities(
    request: Request,
    limit: int = Query(100, ge=1, le=100),
    start: str = Query(None),
    type: str = Query(None),
):
    require_bearer(request)
    all_activities = [_cio_activity(p, i) for i, p in enumerate(PEOPLE[:10])]
    if type:
        all_activities = [a for a in all_activities if a["type"] == type]
    page, next_cursor = cursor_paginate(all_activities, start, limit, id_field="delivery_id")

    result = {"activities": page}
    if next_cursor:
        result["next_cursor"] = next_cursor
    return result


@router.get("/v1/newsletters")
async def list_newsletters(
    request: Request,
    limit: int = Query(100, ge=1, le=100),
    cursor: str = Query(None),
):
    require_bearer(request)
    newsletters = [
        {"id": 501, "name": "July Product Update", "type": "email", "created": 1719500000, "updated": 1720000000, "sent_at": 1720000000, "tags": ["product-update", "monthly"], "recipient_count": 5200},
        {"id": 502, "name": "Q2 Customer Survey", "type": "email", "created": 1717000000, "updated": 1717500000, "sent_at": 1717500000, "tags": ["survey"], "recipient_count": 4800},
    ]
    page, next_cursor = cursor_paginate(newsletters, cursor, limit)

    result = {"newsletters": page}
    if next_cursor:
        result["next_cursor"] = next_cursor
    return result


@router.get("/v1/segments")
async def list_segments(
    request: Request,
    limit: int = Query(100, ge=1, le=100),
    cursor: str = Query(None),
):
    require_bearer(request)
    segments = [
        {"id": 1, "name": "Active Customers", "description": "Customers with active subscriptions", "type": "dynamic", "state": "finished", "progress": 100, "count": 1250},
        {"id": 2, "name": "Churned", "description": "Customers who canceled", "type": "dynamic", "state": "finished", "progress": 100, "count": 87},
        {"id": 3, "name": "Trial Users", "description": "Users in trial period", "type": "dynamic", "state": "finished", "progress": 100, "count": 340},
        {"id": 4, "name": "High MRR", "description": "Customers with MRR > $2000", "type": "manual", "state": "finished", "progress": 100, "count": 45},
    ]
    page, next_cursor = cursor_paginate(segments, cursor, limit)

    result = {"segments": page}
    if next_cursor:
        result["next_cursor"] = next_cursor
    return result
