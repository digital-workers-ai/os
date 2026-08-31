"""
HubSpot CRM v3 mock provider.
Contract: seeds/docs/01-hubspot.md
"""

from fastapi import APIRouter, Request, Query
from seeds.helpers import require_bearer, cursor_paginate
from seeds.world import (
    COMPANIES, PEOPLE, SUBSCRIPTIONS_BY_COMPANY,
    ER_COMPANY_NAMES, ER_PERSON_NAMES, ER_PERSON_EMAILS,
    PEOPLE_BY_COMPANY,
)

router = APIRouter()


def _hs_company(c):
    name = ER_COMPANY_NAMES.get(("hubspot", c.id), c.name)
    return {
        "id": f"hs_company_{c.id[1:].zfill(3)}",
        "properties": {
            "name": name,
            "domain": c.domain,
            "industry": c.industry or "",
            "numberofemployees": str(c.employee_count) if c.employee_count else "",
            "city": c.city or "",
            "state": c.state or "",
            "country": "United States" if c.country == "US" else c.country,
            "createdate": f"{c.created_at}T09:00:00.000Z",
            "hs_lastmodifieddate": "2026-07-01T10:00:00.000Z",
            "hs_object_id": f"hs_company_{c.id[1:].zfill(3)}",
        },
        "createdAt": f"{c.created_at}T09:00:00.000Z",
        "updatedAt": "2026-07-01T10:00:00.000Z",
        "archived": False,
    }


def _hs_contact(p):
    first, last = ER_PERSON_NAMES.get(("hubspot", p.id), (p.first_name, p.last_name))
    email = ER_PERSON_EMAILS.get(("hubspot", p.id), p.email)
    sub = SUBSCRIPTIONS_BY_COMPANY.get(p.company_id)
    lifecycle = "customer" if sub and sub.status in ("active", "past_due", "trialing") else "lead"
    company_name = ER_COMPANY_NAMES.get(("hubspot", p.company_id), None)
    if not company_name:
        from seeds.world import COMPANIES_BY_ID
        comp = COMPANIES_BY_ID.get(p.company_id)
        company_name = comp.name if comp else ""

    return {
        "id": f"hs_contact_{p.id[1:].zfill(3)}",
        "properties": {
            "firstname": first,
            "lastname": last,
            "email": email,
            "createdate": f"{p.created_at}T10:30:00.000Z",
            "lastmodifieddate": "2026-07-01T14:22:00.000Z",
            "lifecyclestage": lifecycle,
            "company": company_name,
            "hs_object_id": f"hs_contact_{p.id[1:].zfill(3)}",
        },
        "createdAt": f"{p.created_at}T10:30:00.000Z",
        "updatedAt": "2026-07-01T14:22:00.000Z",
        "archived": False,
    }


def _hs_deal(company, sub):
    stage = {
        "active": "closedwon",
        "trialing": "qualifiedtobuy",
        "past_due": "closedwon",
        "canceled": "closedlost",
    }.get(sub.status, "appointmentscheduled")

    return {
        "id": f"hs_deal_{sub.id[3:].zfill(3)}",
        "properties": {
            "dealname": f"{company.name} - {sub.plan.title()} Plan",
            "amount": str(sub.mrr_cents * 12 // 100),
            "dealstage": stage,
            "pipeline": "default",
            "closedate": f"{sub.started_at}T00:00:00.000Z",
            "createdate": f"{sub.started_at}T00:00:00.000Z",
            "hs_lastmodifieddate": "2026-07-01T10:00:00.000Z",
            "hs_object_id": f"hs_deal_{sub.id[3:].zfill(3)}",
        },
        "createdAt": f"{sub.started_at}T00:00:00.000Z",
        "updatedAt": "2026-07-01T10:00:00.000Z",
        "archived": False,
    }


# --- OAuth ---

@router.post("/oauth/v1/token")
async def oauth_token(request: Request):
    return {
        "access_token": "mock_hs_access_token_001",
        "refresh_token": "mock_hs_refresh_token_001",
        "expires_in": 1800,
        "token_type": "bearer",
    }


# --- CRM Objects ---

@router.get("/crm/v3/objects/contacts")
async def list_contacts(
    request: Request,
    limit: int = Query(100, ge=1, le=100),
    after: str = Query(None),
    properties: str = Query(None),
    archived: bool = Query(False),
):
    require_bearer(request)
    all_contacts = [_hs_contact(p) for p in PEOPLE]
    page, next_cursor = cursor_paginate(all_contacts, after, limit, id_field="id")

    result = {"results": page}
    if next_cursor:
        result["paging"] = {
            "next": {
                "after": next_cursor,
                "link": f"/crm/v3/objects/contacts?after={next_cursor}",
            }
        }
    return result


@router.get("/crm/v3/objects/companies")
async def list_companies(
    request: Request,
    limit: int = Query(100, ge=1, le=100),
    after: str = Query(None),
    properties: str = Query(None),
    archived: bool = Query(False),
):
    require_bearer(request)
    all_companies = [_hs_company(c) for c in COMPANIES]
    page, next_cursor = cursor_paginate(all_companies, after, limit, id_field="id")

    result = {"results": page}
    if next_cursor:
        result["paging"] = {
            "next": {
                "after": next_cursor,
                "link": f"/crm/v3/objects/companies?after={next_cursor}",
            }
        }
    return result


@router.get("/crm/v3/objects/deals")
async def list_deals(
    request: Request,
    limit: int = Query(100, ge=1, le=100),
    after: str = Query(None),
    properties: str = Query(None),
    archived: bool = Query(False),
):
    require_bearer(request)
    from seeds.world import COMPANIES_BY_ID
    all_deals = []
    for sub in __import__("seeds.world", fromlist=["SUBSCRIPTIONS"]).SUBSCRIPTIONS:
        company = COMPANIES_BY_ID.get(sub.company_id)
        if company:
            all_deals.append(_hs_deal(company, sub))

    page, next_cursor = cursor_paginate(all_deals, after, limit, id_field="id")

    result = {"results": page}
    if next_cursor:
        result["paging"] = {
            "next": {
                "after": next_cursor,
                "link": f"/crm/v3/objects/deals?after={next_cursor}",
            }
        }
    return result
