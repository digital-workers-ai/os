"""
ActiveCampaign API v3 mock provider.
Contract: seeds/docs/19-activecampaign.md

Api-Token header auth. Offset pagination. String number IDs.
Campaign status: "0"=draft, "1"=scheduled, "2"=sending, "3"=paused, "4"=stopped, "5"=completed.
"""

from fastapi import APIRouter, Request, Query
from seeds.helpers import require_header, offset_paginate
from seeds.world import PEOPLE, COMPANIES_BY_ID, EMAIL_CAMPAIGNS, SUBSCRIPTIONS_BY_COMPANY

router = APIRouter()

_STATUS_MAP = {"draft": "0", "scheduled": "1", "sending": "2", "sent": "5"}


def _ac_auth(request: Request):
    require_header(request, "api-token")


def _ac_contact(p, idx):
    co = COMPANIES_BY_ID.get(p.company_id)
    return {
        "id": str(idx + 1), "email": p.email,
        "firstName": p.first_name, "lastName": p.last_name,
        "phone": p.phone or "",
        "orgname": co.name if co else "",
        "cdate": f"{p.created_at}T00:00:00-05:00",
        "udate": f"{p.last_seen}T00:00:00-05:00" if p.last_seen else f"{p.created_at}T00:00:00-05:00",
        "links": {
            "bounceLogs": f"/api/3/contacts/{idx+1}/bounceLogs",
            "contactAutomations": f"/api/3/contacts/{idx+1}/contactAutomations",
            "contactData": f"/api/3/contacts/{idx+1}/contactData",
            "contactDeals": f"/api/3/contacts/{idx+1}/contactDeals",
            "contactLists": f"/api/3/contacts/{idx+1}/contactLists",
            "contactTags": f"/api/3/contacts/{idx+1}/contactTags",
        },
    }


def _ac_campaign(ec, idx):
    return {
        "id": str(idx + 1), "type": "single", "name": ec.name,
        "sdate": ec.sent_at or "", "status": _STATUS_MAP.get(ec.status, "0"),
        "send_amt": str(ec.sends), "total_amt": str(ec.sends),
        "opens": str(ec.opens), "uniqueopens": str(int(ec.opens * 0.85)),
        "linkclicks": str(ec.clicks), "uniquelinkclicks": str(int(ec.clicks * 0.9)),
        "subscriberclicks": str(int(ec.clicks * 0.85)),
        "hardbounces": str(int(ec.bounces * 0.3)), "softbounces": str(int(ec.bounces * 0.7)),
        "unsubscribes": str(ec.unsubscribes),
        "cdate": "2026-06-20T10:00:00-05:00",
        "mdate": ec.sent_at or "2026-06-20T10:00:00-05:00",
        "links": {"campaignMessage": f"/api/3/campaigns/{idx+1}/campaignMessage"},
    }


@router.get("/api/3/contacts")
async def list_contacts(request: Request, limit: int = Query(20, le=100), offset: int = Query(0)):
    _ac_auth(request)
    contacts = [_ac_contact(p, i) for i, p in enumerate(PEOPLE)]
    page, total = offset_paginate(contacts, offset, limit)
    return {"contacts": page, "meta": {"total": str(total)}}


@router.get("/api/3/automations")
async def list_automations(request: Request, limit: int = Query(20, le=100), offset: int = Query(0)):
    _ac_auth(request)
    automations = [
        {"id": "1", "name": "Welcome Series", "status": "1", "entered": "342", "exited": "310", "cdate": "2025-02-01T10:00:00-05:00", "mdate": "2026-07-10T08:00:00-05:00", "links": {"campaigns": "/api/3/automations/1/campaigns", "contactGoals": "/api/3/automations/1/contactGoals"}},
        {"id": "2", "name": "Lead Nurture - Enterprise", "status": "1", "entered": "120", "exited": "85", "cdate": "2025-04-15T14:00:00-05:00", "mdate": "2026-07-08T09:00:00-05:00", "links": {"campaigns": "/api/3/automations/2/campaigns"}},
        {"id": "3", "name": "Churn Prevention", "status": "1", "entered": "45", "exited": "12", "cdate": "2025-09-01T08:00:00-05:00", "mdate": "2026-07-12T11:00:00-05:00", "links": {"campaigns": "/api/3/automations/3/campaigns"}},
    ]
    page, total = offset_paginate(automations, offset, limit)
    return {"automations": page, "meta": {"total": str(total)}}


@router.get("/api/3/deals")
async def list_deals(request: Request, limit: int = Query(20, le=100), offset: int = Query(0)):
    _ac_auth(request)
    deals = [
        {"id": "1", "title": "Acme Corp - Enterprise Upgrade", "value": "480000", "currency": "usd", "contact": "1", "organization": "1", "stage": "3", "status": "0", "cdate": "2026-06-15T10:00:00-05:00", "mdate": "2026-07-14T09:00:00-05:00", "links": {"activities": "/api/3/deals/1/activities", "contact": "/api/3/deals/1/contact", "contactDeals": "/api/3/deals/1/contactDeals"}},
        {"id": "2", "title": "Wayne Enterprises - Professional", "value": "180000", "currency": "usd", "contact": "11", "organization": "5", "stage": "2", "status": "0", "cdate": "2026-07-01T11:00:00-05:00", "mdate": "2026-07-12T14:00:00-05:00", "links": {"activities": "/api/3/deals/2/activities"}},
        {"id": "3", "title": "Globex Inc - Renewal", "value": "240000", "currency": "usd", "contact": "4", "organization": "2", "stage": "4", "status": "1", "cdate": "2026-05-20T08:00:00-05:00", "mdate": "2026-07-01T10:00:00-05:00", "links": {"activities": "/api/3/deals/3/activities"}},
    ]
    page, total = offset_paginate(deals, offset, limit)
    total_value = sum(int(d["value"]) for d in deals)
    return {"deals": page, "meta": {"total": str(total), "currencies": [{"currency": "usd", "total": str(total_value)}]}}


@router.get("/api/3/campaigns")
async def list_campaigns(request: Request, limit: int = Query(20, le=100), offset: int = Query(0)):
    _ac_auth(request)
    campaigns = [_ac_campaign(ec, i) for i, ec in enumerate(EMAIL_CAMPAIGNS)]
    page, total = offset_paginate(campaigns, offset, limit)
    return {"campaigns": page, "meta": {"total": str(total)}}
