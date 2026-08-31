"""
SendGrid API v3 mock provider.
Contract: seeds/docs/20-sendgrid.md

Bearer auth. Mixed pagination (token for singlesends, none for contacts/stats).
Stats returns flat array.
"""

from fastapi import APIRouter, Request, Query
from seeds.helpers import require_bearer, token_paginate
from seeds.world import PEOPLE, COMPANIES_BY_ID, EMAIL_CAMPAIGNS

router = APIRouter()


def _sg_contact(p):
    co = COMPANIES_BY_ID.get(p.company_id)
    return {
        "id": f"sg_contact_{p.id}",
        "email": p.email, "first_name": p.first_name, "last_name": p.last_name,
        "phone_number": p.phone,
        "alternate_emails": [],
        "custom_fields": {"company": co.name if co else "", "role": p.role or ""},
        "created_at": f"{p.created_at}T00:00:00Z",
        "updated_at": f"{p.last_seen}T00:00:00Z" if p.last_seen else f"{p.created_at}T00:00:00Z",
        "list_ids": ["sg_list_001"],
    }


def _sg_singlesend(ec):
    status_map = {"draft": "draft", "scheduled": "scheduled", "sending": "triggered", "sent": "triggered"}
    return {
        "id": f"sg_ss_{ec.id}", "name": ec.name,
        "status": status_map.get(ec.status, "draft"),
        "categories": [],
        "send_at": ec.sent_at,
        "created_at": "2026-06-20T10:00:00Z",
        "updated_at": ec.sent_at or "2026-06-20T10:00:00Z",
        "email_config": {"subject": ec.subject, "sender_id": 12345, "suppression_group_id": None},
        "stats": {
            "requests": ec.sends, "delivered": int(ec.sends * 0.97), "opens": ec.opens,
            "unique_opens": int(ec.opens * 0.85), "clicks": ec.clicks,
            "unique_clicks": int(ec.clicks * 0.9), "bounces": int(ec.sends * 0.02),
            "unsubscribes": int(ec.sends * 0.005), "spam_reports": 0,
        },
    }


@router.get("/v3/marketing/contacts")
async def list_contacts(request: Request):
    require_bearer(request)
    contacts = [_sg_contact(p) for p in PEOPLE[:10]]
    return {
        "result": contacts,
        "contact_count": len(contacts),
        "_metadata": {"self": "/v3/marketing/contacts"},
    }


@router.get("/v3/marketing/singlesends")
async def list_singlesends(request: Request, page_token: str = Query(None), page_size: int = Query(25)):
    require_bearer(request)
    sends = [_sg_singlesend(ec) for ec in EMAIL_CAMPAIGNS]
    page, next_token = token_paginate(sends, page_token, page_size)
    return {
        "result": page,
        "_metadata": {
            "self": "/v3/marketing/singlesends",
            "next": f"/v3/marketing/singlesends?page_token={next_token}&page_size={page_size}" if next_token else None,
            "prev": None,
            "count": len(sends),
        },
    }


@router.get("/v3/stats")
async def global_stats(request: Request, start_date: str = Query(...), end_date: str = Query(None)):
    require_bearer(request)
    return [
        {"date": "2026-07-01", "stats": [{"type": "category", "name": "all", "metrics": {"blocks": 2, "bounce_drops": 5, "bounces": 23, "clicks": 342, "deferred": 12, "delivered": 4477, "invalid_emails": 3, "opens": 1890, "processed": 4500, "requests": 4500, "spam_report_drops": 0, "spam_reports": 1, "unique_clicks": 310, "unique_opens": 1610, "unsubscribe_drops": 0, "unsubscribes": 8}}]},
        {"date": "2026-07-02", "stats": [{"type": "category", "name": "all", "metrics": {"blocks": 1, "bounce_drops": 3, "bounces": 18, "clicks": 580, "deferred": 8, "delivered": 4182, "invalid_emails": 2, "opens": 2100, "processed": 4200, "requests": 4200, "spam_report_drops": 0, "spam_reports": 0, "unique_clicks": 520, "unique_opens": 1785, "unsubscribe_drops": 0, "unsubscribes": 5}}]},
    ]


@router.get("/v3/marketing/lists")
async def list_lists(request: Request, page_token: str = Query(None), page_size: int = Query(25)):
    require_bearer(request)
    all_lists = [
        {"id": "sg_list_001", "name": "Main Newsletter", "contact_count": 4500, "created_at": "2025-06-01T10:00:00Z", "updated_at": "2026-07-01T10:00:00Z", "_metadata": {"self": "/v3/marketing/lists/sg_list_001"}},
        {"id": "sg_list_002", "name": "Product Updates", "contact_count": 2100, "created_at": "2025-08-15T14:00:00Z", "updated_at": "2026-06-20T10:00:00Z", "_metadata": {"self": "/v3/marketing/lists/sg_list_002"}},
        {"id": "sg_list_003", "name": "Beta Testers", "contact_count": 350, "created_at": "2026-01-10T09:00:00Z", "updated_at": "2026-07-10T10:00:00Z", "_metadata": {"self": "/v3/marketing/lists/sg_list_003"}},
    ]
    page, next_token = token_paginate(all_lists, page_token, page_size)
    return {
        "result": page,
        "_metadata": {
            "self": "/v3/marketing/lists",
            "next": f"/v3/marketing/lists?page_token={next_token}&page_size={page_size}" if next_token else None,
            "prev": None,
            "count": len(all_lists),
        },
    }
