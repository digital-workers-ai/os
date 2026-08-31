"""
Zendesk Support API v2 mock provider.
Contract: seeds/docs/28-zendesk.md

Basic Auth or Bearer. Cursor pagination (page[after] / meta.after_cursor).
Named keys (tickets, users, organizations). Tags as flat string arrays.
"""

import base64
from fastapi import APIRouter, Request, Query
from seeds.helpers import require_bearer, require_basic_auth
from seeds.world import PEOPLE, COMPANIES, COMPANIES_BY_ID, TICKETS, SUBSCRIPTIONS_BY_COMPANY, PEOPLE_BY_COMPANY

router = APIRouter()


def _zd_auth(request: Request):
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        require_bearer(request)
    elif auth.startswith("Basic "):
        require_basic_auth(request)
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail={"error": "Couldn't authenticate you"})


def _zd_cursor_paginate(items, after, size):
    start_idx = 0
    if after:
        try:
            start_idx = int(base64.b64decode(after).decode())
        except Exception:
            start_idx = 0
    page = items[start_idx:start_idx + size]
    has_more = start_idx + size < len(items)
    after_cursor = base64.b64encode(str(start_idx + size).encode()).decode() if has_more else None
    before_cursor = base64.b64encode(str(start_idx).encode()).decode() if start_idx > 0 else None
    meta = {"has_more": has_more, "after_cursor": after_cursor, "before_cursor": before_cursor}
    links = {
        "next": f"?page[after]={after_cursor}" if after_cursor else None,
        "prev": f"?page[before]={before_cursor}" if before_cursor else None,
    }
    return page, meta, links, len(items)


def _zd_ticket(t, idx):
    p = next((pp for pp in PEOPLE if pp.id == t.requester_id), None)
    co = COMPANIES_BY_ID.get(t.company_id)
    type_map = {"high": "problem", "urgent": "problem", "normal": "question", "low": "question"}
    return {
        "id": 1000 + idx + 1,
        "url": f"https://mock.zendesk.com/api/v2/tickets/{1000 + idx + 1}.json",
        "external_id": None,
        "type": type_map.get(t.priority, "question"),
        "subject": t.subject, "raw_subject": t.subject,
        "description": t.subject,
        "priority": t.priority, "status": t.status,
        "requester_id": 20000 + idx + 1,
        "submitter_id": 20000 + idx + 1,
        "assignee_id": 30001,
        "organization_id": 40000 + int(t.company_id.replace("c", "")),
        "group_id": 50001,
        "tags": [t.priority, t.channel, t.status],
        "custom_fields": [
            {"id": 360001, "value": co.domain if co else ""},
            {"id": 360002, "value": ""},
        ],
        "via": {
            "channel": t.channel,
            "source": {
                "from": {"address": p.email if p else "", "name": f"{p.first_name} {p.last_name}" if p else ""},
                "to": {"name": "Support", "address": "support@acme.io"},
            },
        },
        "created_at": t.created_at, "updated_at": t.updated_at,
    }


def _zd_user(p, idx):
    co = COMPANIES_BY_ID.get(p.company_id)
    sub = SUBSCRIPTIONS_BY_COMPANY.get(co.id) if co else None
    return {
        "id": 20000 + idx + 1,
        "url": f"https://mock.zendesk.com/api/v2/users/{20000 + idx + 1}.json",
        "name": f"{p.first_name} {p.last_name}",
        "email": p.email,
        "created_at": f"{p.created_at}T00:00:00Z",
        "updated_at": f"{p.last_seen}T00:00:00Z" if p.last_seen else f"{p.created_at}T00:00:00Z",
        "phone": p.phone, "role": "end-user",
        "verified": True, "active": True,
        "external_id": f"user_{p.first_name.lower()}_{co.domain.split('.')[0]}" if co else f"user_{p.id}",
        "organization_id": 40000 + int(p.company_id.replace("c", "")),
        "tags": ["customer"],
        "user_fields": {
            "company_domain": co.domain if co else "",
            "plan": sub.plan if sub else "free",
            "mrr": sub.mrr_cents / 100 if sub else 0,
        },
    }


def _zd_org(c, idx):
    sub = SUBSCRIPTIONS_BY_COMPANY.get(c.id)
    return {
        "id": 40000 + int(c.id.replace("c", "")),
        "url": f"https://mock.zendesk.com/api/v2/organizations/{40000 + int(c.id.replace('c', ''))}.json",
        "name": c.name,
        "shared_tickets": False, "shared_comments": False,
        "external_id": c.domain,
        "created_at": f"{c.created_at}T00:00:00Z",
        "updated_at": "2026-07-10T14:00:00Z",
        "domain_names": [c.domain],
        "details": f"{c.industry or 'Company'}, {sub.plan.capitalize() if sub else 'Free'} plan",
        "tags": ["customer"],
        "organization_fields": {
            "plan": sub.plan if sub else "free",
            "mrr": sub.mrr_cents / 100 if sub else 0,
            "industry": c.industry,
            "employee_count": c.employee_count,
        },
    }


@router.get("/tickets.json")
async def list_tickets(
    request: Request,
    page_size: int = Query(100, alias="page[size]", ge=1, le=100),
    page_after: str = Query(None, alias="page[after]"),
    sort: str = Query(None),
):
    _zd_auth(request)
    tickets = [_zd_ticket(t, i) for i, t in enumerate(TICKETS)]
    page, meta, links, count = _zd_cursor_paginate(tickets, page_after, page_size)
    return {"tickets": page, "meta": meta, "links": links, "count": count}


@router.get("/users.json")
async def list_users(
    request: Request,
    page_size: int = Query(100, alias="page[size]", ge=1, le=100),
    page_after: str = Query(None, alias="page[after]"),
    role: str = Query(None),
):
    _zd_auth(request)
    users = [_zd_user(p, i) for i, p in enumerate(PEOPLE)]
    if role:
        users = [u for u in users if u["role"] == role]
    page, meta, links, count = _zd_cursor_paginate(users, page_after, page_size)
    return {"users": page, "meta": meta, "links": links, "count": count}


@router.get("/organizations.json")
async def list_organizations(
    request: Request,
    page_size: int = Query(100, alias="page[size]", ge=1, le=100),
    page_after: str = Query(None, alias="page[after]"),
):
    _zd_auth(request)
    orgs = [_zd_org(c, i) for i, c in enumerate(COMPANIES)]
    page, meta, links, count = _zd_cursor_paginate(orgs, page_after, page_size)
    return {"organizations": page, "meta": meta, "links": links, "count": count}


@router.get("/search.json")
async def search(
    request: Request,
    query: str = Query(...),
    page_size: int = Query(100, alias="page[size]", ge=1, le=100),
    page_after: str = Query(None, alias="page[after]"),
):
    _zd_auth(request)
    results = []
    q = query.lower()
    if "type:ticket" in q:
        tickets = [_zd_ticket(t, i) for i, t in enumerate(TICKETS)]
        for t in tickets:
            if "status:" in q:
                status = q.split("status:")[1].split()[0]
                if t["status"] != status:
                    continue
            t["result_type"] = "ticket"
            results.append(t)
    elif "type:user" in q:
        users = [_zd_user(p, i) for i, p in enumerate(PEOPLE)]
        for u in users:
            u["result_type"] = "user"
            results.append(u)
    elif "type:organization" in q:
        orgs = [_zd_org(c, i) for i, c in enumerate(COMPANIES)]
        for o in orgs:
            o["result_type"] = "organization"
            results.append(o)
    else:
        tickets = [_zd_ticket(t, i) for i, t in enumerate(TICKETS)]
        for t in tickets:
            t["result_type"] = "ticket"
            results.append(t)

    return {"results": results, "facets": None, "count": len(results), "next_page": None, "previous_page": None}
