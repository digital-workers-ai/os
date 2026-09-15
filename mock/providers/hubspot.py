"""
HubSpot CRM v3 mock provider.
Contract: seeds/docs/01-hubspot.md
"""

from fastapi import APIRouter, Request, Query
from seeds.helpers import require_bearer, cursor_paginate
from seeds.world import (
    COMPANIES, PEOPLE, SUBSCRIPTIONS, SUBSCRIPTIONS_BY_COMPANY, COMPANIES_BY_ID,
    ER_COMPANY_NAMES, ER_PERSON_NAMES, ER_PERSON_EMAILS,
)

router = APIRouter()

PORTAL_ID = 12345678

COMPANY_ID_BASE = 346000000000
CONTACT_ID_BASE = 550000000000
DEAL_ID_BASE = 348000000000

OBJECT_TYPE_ID = {"contacts": "0-1", "companies": "0-2", "deals": "0-3"}

ALWAYS_RETURNED = {
    "contacts": ("createdate", "hs_object_id", "lastmodifieddate"),
    "companies": ("createdate", "hs_lastmodifieddate", "hs_object_id"),
    "deals": ("createdate", "hs_lastmodifieddate", "hs_object_id"),
}

INDUSTRY_VALUES = {
    "Software": "COMPUTER_SOFTWARE",
    "Marketing": "MARKETING_AND_ADVERTISING",
    "Finance": "FINANCIAL_SERVICES",
    "Healthcare": "HOSPITAL_HEALTH_CARE",
    "Manufacturing": "MACHINERY",
    "Technology": "INFORMATION_TECHNOLOGY_AND_SERVICES",
    "Engineering": "MECHANICAL_OR_INDUSTRIAL_ENGINEERING",
    "Food & Beverage": "FOOD_AND_BEVERAGES",
}

COMPANIES_KNOWN_ONLY_BY_DOMAIN = {"c9"}

WON_SUBSCRIPTION_STATUSES = ("active", "past_due")
LOST_SUBSCRIPTION_STATUSES = ("canceled",)


def _requested(properties):
    return {p.strip() for p in properties.split(",") if p.strip()} if properties else set()


def _record(object_type, record_id, properties, created_at, updated_at, requested):
    returned = set(ALWAYS_RETURNED[object_type]) | requested
    return {
        "id": record_id,
        "properties": {k: v for k, v in properties.items() if k in returned},
        "createdAt": created_at,
        "updatedAt": updated_at,
        "archived": False,
        "url": (
            f"https://app-na2.hubspot.com/contacts/{PORTAL_ID}"
            f"/record/{OBJECT_TYPE_ID[object_type]}/{record_id}"
        ),
    }


def _hs_company(c, requested):
    record_id = str(COMPANY_ID_BASE + int(c.id[1:]))
    name = ER_COMPANY_NAMES.get(("hubspot", c.id), c.name)
    if c.id in COMPANIES_KNOWN_ONLY_BY_DOMAIN:
        name = None
    created_at = f"{c.created_at}T09:00:00.000Z"
    updated_at = "2026-07-01T10:00:00.000Z"
    properties = {
        "name": name,
        "domain": c.domain,
        "industry": INDUSTRY_VALUES.get(c.industry),
        "numberofemployees": str(c.employee_count) if c.employee_count else None,
        "city": c.city,
        "state": c.state,
        "country": "United States" if c.country == "US" else c.country,
        "createdate": created_at,
        "hs_lastmodifieddate": updated_at,
        "hs_object_id": record_id,
    }
    return _record("companies", record_id, properties, created_at, updated_at, requested)


def _hs_contact(p, requested):
    record_id = str(CONTACT_ID_BASE + int(p.id[1:]))
    first, last = ER_PERSON_NAMES.get(("hubspot", p.id), (p.first_name, p.last_name))
    email = ER_PERSON_EMAILS.get(("hubspot", p.id), p.email)
    sub = SUBSCRIPTIONS_BY_COMPANY.get(p.company_id)
    lifecycle = "customer" if sub and sub.status in ("active", "past_due", "trialing") else "lead"
    company_name = ER_COMPANY_NAMES.get(("hubspot", p.company_id), None)
    if not company_name:
        comp = COMPANIES_BY_ID.get(p.company_id)
        company_name = comp.name if comp else None
    created_at = f"{p.created_at}T10:30:00.000Z"
    updated_at = "2026-07-01T14:22:00.000Z"
    properties = {
        "firstname": first,
        "lastname": last,
        "email": email,
        "createdate": created_at,
        "lastmodifieddate": updated_at,
        "lifecyclestage": lifecycle,
        "company": company_name,
        "hs_object_id": record_id,
    }
    return _record("contacts", record_id, properties, created_at, updated_at, requested)


def _hs_deal(company, sub, requested):
    record_id = str(DEAL_ID_BASE + int(sub.id[3:]))
    won = sub.status in WON_SUBSCRIPTION_STATUSES
    closed = won or sub.status in LOST_SUBSCRIPTION_STATUSES
    stage = {
        "active": "closedwon",
        "trialing": "qualifiedtobuy",
        "past_due": "closedwon",
        "canceled": "closedlost",
    }.get(sub.status, "appointmentscheduled")
    created_at = f"{sub.started_at}T00:00:00.000Z"
    updated_at = "2026-07-01T10:00:00.000Z"
    properties = {
        "dealname": f"{company.name} - {sub.plan.title()} Plan",
        "amount": str(sub.mrr_cents * 12 // 100),
        "deal_currency_code": None,
        "dealstage": stage,
        "hs_is_closed_won": "true" if won else "false",
        "hs_is_closed": "true" if closed else "false",
        "pipeline": "default",
        "closedate": created_at,
        "createdate": created_at,
        "hs_lastmodifieddate": updated_at,
        "hs_object_id": record_id,
    }
    return _record("deals", record_id, properties, created_at, updated_at, requested)


def _page(request, rows, after, limit):
    page, next_cursor = cursor_paginate(rows, after, limit, id_field="id")
    result = {"results": page}
    if next_cursor:
        result["paging"] = {
            "next": {
                "after": next_cursor,
                "link": str(request.url.include_query_params(after=next_cursor)),
            }
        }
    return result


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
    requested = _requested(properties)
    return _page(request, [_hs_contact(p, requested) for p in PEOPLE], after, limit)


@router.get("/crm/v3/objects/companies")
async def list_companies(
    request: Request,
    limit: int = Query(100, ge=1, le=100),
    after: str = Query(None),
    properties: str = Query(None),
    archived: bool = Query(False),
):
    require_bearer(request)
    requested = _requested(properties)
    return _page(request, [_hs_company(c, requested) for c in COMPANIES], after, limit)


@router.get("/crm/v3/objects/deals")
async def list_deals(
    request: Request,
    limit: int = Query(100, ge=1, le=100),
    after: str = Query(None),
    properties: str = Query(None),
    archived: bool = Query(False),
):
    require_bearer(request)
    requested = _requested(properties)
    rows = []
    for sub in SUBSCRIPTIONS:
        company = COMPANIES_BY_ID.get(sub.company_id)
        if company:
            rows.append(_hs_deal(company, sub, requested))
    return _page(request, rows, after, limit)
