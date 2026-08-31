"""
Salesforce REST API v67.0 mock provider.
Contract: seeds/docs/12-salesforce.md

SOQL query endpoint with cursor-chain pagination (nextRecordsUrl).
ER variations applied via ER_COMPANY_NAMES/ER_PERSON_NAMES.
"""

import re
from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import JSONResponse
from seeds.world import (
    COMPANIES, COMPANIES_BY_ID, PEOPLE, PEOPLE_BY_COMPANY,
    SUBSCRIPTIONS_BY_COMPANY, TICKETS,
    ER_COMPANY_NAMES, ER_PERSON_NAMES, ER_PERSON_EMAILS,
)

router = APIRouter()

_SF_PREFIX = "/services/data/v67.0"


def _sf_auth(request: Request):
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer ") or len(auth) <= 7:
        raise HTTPException(status_code=401, detail=[{"message": "Session expired or invalid", "errorCode": "INVALID_SESSION_ID"}])


def _sf_id(prefix, raw_id):
    num = raw_id.lstrip("cpsub").zfill(6)
    return f"{prefix}xx000003DGb{num}"


def _sf_account(c):
    name = ER_COMPANY_NAMES.get(("salesforce", c.id), c.name)
    sub = SUBSCRIPTIONS_BY_COMPANY.get(c.id)
    revenue = sub.mrr_cents * 12 / 100 if sub else None
    return {
        "attributes": {"type": "Account", "url": f"{_SF_PREFIX}/sobjects/Account/{_sf_id('001', c.id)}"},
        "Id": _sf_id("001", c.id),
        "Name": name,
        "Industry": c.industry or "Technology",
        "Website": f"https://{c.domain}",
        "AnnualRevenue": revenue,
        "NumberOfEmployees": c.employee_count,
        "BillingCity": c.city,
        "BillingState": c.state,
        "BillingCountry": "United States" if c.country == "US" else c.country,
        "CreatedDate": f"{c.created_at}T10:30:00.000+0000",
    }


def _sf_contact(p):
    acct_id = _sf_id("001", p.company_id)
    company = COMPANIES_BY_ID.get(p.company_id)
    company_name = ER_COMPANY_NAMES.get(("salesforce", p.company_id), company.name if company else "Unknown")
    first, last = ER_PERSON_NAMES.get(("salesforce", p.id), (p.first_name, p.last_name))
    email = ER_PERSON_EMAILS.get(("salesforce", p.id), p.email)
    return {
        "attributes": {"type": "Contact", "url": f"{_SF_PREFIX}/sobjects/Contact/{_sf_id('003', p.id)}"},
        "Id": _sf_id("003", p.id),
        "FirstName": first,
        "LastName": last,
        "Email": email,
        "Phone": p.phone,
        "Title": p.role,
        "AccountId": acct_id,
        "Account": {
            "attributes": {"type": "Account", "url": f"{_SF_PREFIX}/sobjects/Account/{acct_id}"},
            "Name": company_name,
        },
        "CreatedDate": f"{p.created_at}T09:00:00.000+0000",
    }


def _sf_opportunity(c):
    sub = SUBSCRIPTIONS_BY_COMPANY.get(c.id)
    if not sub:
        return None
    stage_map = {"active": "Negotiation/Review", "trialing": "Prospecting", "past_due": "Negotiation/Review", "canceled": "Closed Lost"}
    return {
        "attributes": {"type": "Opportunity", "url": f"{_SF_PREFIX}/sobjects/Opportunity/{_sf_id('006', c.id)}"},
        "Id": _sf_id("006", c.id),
        "Name": f"{c.name} - Enterprise Upgrade",
        "StageName": stage_map.get(sub.status, "Qualification"),
        "Amount": sub.mrr_cents * 12 / 100,
        "CloseDate": "2026-08-15",
        "Probability": 75 if sub.status == "active" else 25,
        "AccountId": _sf_id("001", c.id),
        "Account": {
            "attributes": {"type": "Account", "url": f"{_SF_PREFIX}/sobjects/Account/{_sf_id('001', c.id)}"},
            "Name": ER_COMPANY_NAMES.get(("salesforce", c.id), c.name),
        },
    }


def _detect_object(query: str) -> str:
    q = query.upper()
    if "FROM CONTACT" in q:
        return "Contact"
    if "FROM OPPORTUNITY" in q:
        return "Opportunity"
    if "FROM LEAD" in q:
        return "Lead"
    if "FROM CASE" in q:
        return "Case"
    return "Account"


def _run_query(query: str) -> list:
    obj = _detect_object(query)
    if obj == "Account":
        return [_sf_account(c) for c in COMPANIES]
    elif obj == "Contact":
        return [_sf_contact(p) for p in PEOPLE]
    elif obj == "Opportunity":
        return [r for r in (_sf_opportunity(c) for c in COMPANIES) if r is not None]
    return []


@router.get("/query")
async def soql_query(request: Request, q: str = Query(...)):
    _sf_auth(request)
    records = _run_query(q)
    return {"totalSize": len(records), "done": True, "records": records}


@router.get("/query/{query_locator}")
async def soql_query_more(request: Request, query_locator: str):
    _sf_auth(request)
    return {"totalSize": 0, "done": True, "records": []}


@router.get("/sobjects/{object_name}")
async def describe_object(request: Request, object_name: str):
    _sf_auth(request)
    prefix_map = {"Account": "001", "Contact": "003", "Opportunity": "006", "Lead": "00Q", "Case": "500"}
    return {
        "objectDescribe": {
            "name": object_name,
            "label": object_name,
            "labelPlural": f"{object_name}s",
            "keyPrefix": prefix_map.get(object_name, "000"),
            "custom": False,
            "urls": {
                "sobject": f"{_SF_PREFIX}/sobjects/{object_name}",
                "describe": f"{_SF_PREFIX}/sobjects/{object_name}/describe",
                "rowTemplate": f"{_SF_PREFIX}/sobjects/{object_name}/{{ID}}",
            },
        },
        "recentItems": [],
    }


@router.get("/limits")
async def limits(request: Request):
    _sf_auth(request)
    return {
        "DailyApiRequests": {"Max": 100000, "Remaining": 94523},
        "DailyBulkApiRequests": {"Max": 15000, "Remaining": 15000},
        "DailyBulkV2QueryJobs": {"Max": 10000, "Remaining": 10000},
        "DataStorageMB": {"Max": 1024, "Remaining": 780},
        "FileStorageMB": {"Max": 1024, "Remaining": 950},
        "SingleEmail": {"Max": 5000, "Remaining": 4980},
        "ConcurrentAsyncGetReportInstances": {"Max": 200, "Remaining": 200},
        "ConcurrentSyncReportRuns": {"Max": 20, "Remaining": 20},
        "HourlyDashboardRefreshes": {"Max": 200, "Remaining": 200},
        "MassEmail": {"Max": 5000, "Remaining": 5000},
        "StreamingApiConcurrentClients": {"Max": 2000, "Remaining": 2000},
    }
