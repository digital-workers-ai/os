"""
Intercom API v2.15 mock provider.
Contract: seeds/docs/27-intercom.md

Bearer + Intercom-Version header. Cursor pagination (starting_after).
Unix timestamps. Nested type/list structures.
"""

from fastapi import APIRouter, Request, Query
from seeds.helpers import require_bearer, require_header
from seeds.world import PEOPLE, COMPANIES, COMPANIES_BY_ID, TICKETS, SUBSCRIPTIONS_BY_COMPANY

router = APIRouter()


def _ic_auth(request: Request):
    require_bearer(request)
    require_header(request, "intercom-version")


def _ic_contact(p, idx):
    co = COMPANIES_BY_ID.get(p.company_id)
    sub = SUBSCRIPTIONS_BY_COMPANY.get(co.id) if co else None
    return {
        "type": "contact", "id": f"con_{p.id}",
        "workspace_id": "ws_mock_001",
        "external_id": f"user_{p.first_name.lower()}_{co.domain.split('.')[0]}" if co else f"user_{p.id}",
        "role": "user", "email": p.email, "phone": p.phone,
        "name": f"{p.first_name} {p.last_name}",
        "created_at": 1710500000 + idx * 86400,
        "updated_at": 1720454400,
        "signed_up_at": 1710500000 + idx * 86400,
        "last_seen_at": 1720454400,
        "browser": "Chrome", "browser_version": "126.0.0", "os": "Mac OS X 14.5",
        "location": {
            "type": "location",
            "country": "United States", "region": co.state if co else "CA",
            "city": co.city if co else "San Francisco", "country_code": "US",
        },
        "custom_attributes": {
            "company": co.name if co else "",
            "plan": sub.plan if sub else "free",
            "mrr": sub.mrr_cents / 100 if sub else 0,
            "company_domain": co.domain if co else "",
        },
        "tags": {"type": "list", "data": [], "total_count": 0, "has_more": False},
        "companies": {
            "type": "list",
            "data": [{"type": "company", "id": f"comp_{co.id}", "name": co.name, "company_id": co.domain}] if co else [],
            "total_count": 1 if co else 0, "has_more": False,
        },
    }


def _ic_company(c, idx):
    sub = SUBSCRIPTIONS_BY_COMPANY.get(c.id)
    return {
        "type": "company", "id": f"comp_{c.id}",
        "company_id": c.domain, "name": c.name,
        "created_at": 1710500000 + idx * 86400,
        "updated_at": 1720454400,
        "remote_created_at": 1710500000 + idx * 86400,
        "last_request_at": 1720454400,
        "monthly_spend": sub.mrr_cents / 100 if sub else 0,
        "session_count": 342 - idx * 20,
        "user_count": len([p for p in PEOPLE if p.company_id == c.id]),
        "size": c.employee_count,
        "website": f"https://{c.domain}", "industry": c.industry,
        "plan": {"type": "plan", "id": f"plan_{sub.plan}" if sub else "plan_free", "name": sub.plan.capitalize() if sub else "Free"},
        "custom_attributes": {
            "domain": c.domain,
            "mrr": sub.mrr_cents / 100 if sub else 0,
            "health_score": 85 - idx * 5,
        },
    }


def _ic_conversation(t, idx):
    p = next((pp for pp in PEOPLE if pp.id == t.requester_id), None)
    co = COMPANIES_BY_ID.get(t.company_id)
    return {
        "type": "conversation", "id": f"conv_{t.id}",
        "created_at": 1720108800 + idx * 86400,
        "updated_at": 1720368000 + idx * 86400,
        "title": t.subject, "state": "open" if t.status in ("open", "new") else "closed",
        "open": t.status in ("open", "new"),
        "priority": "priority" if t.priority in ("high", "urgent") else "not_priority",
        "source": {
            "type": "conversation", "id": f"conv_{t.id}",
            "delivered_as": "customer_initiated", "subject": "",
            "body": f"<p>{t.subject}</p>",
            "author": {"type": "user", "id": f"con_{t.requester_id}", "name": f"{p.first_name} {p.last_name}" if p else "", "email": p.email if p else ""},
        },
        "contacts": {
            "type": "contact.list",
            "contacts": [{"type": "contact", "id": f"con_{t.requester_id}", "external_id": f"user_{p.first_name.lower()}_{co.domain.split('.')[0]}" if p and co else ""}],
        },
        "tags": {"type": "tag.list", "tags": []},
        "statistics": {
            "type": "conversation_statistics",
            "time_to_assignment": 120, "time_to_admin_reply": 300,
            "time_to_first_close": 7200, "count_assignments": 1,
        },
    }


@router.get("/contacts")
async def list_contacts(request: Request, starting_after: str = Query(None), per_page: int = Query(50, ge=1, le=150)):
    _ic_auth(request)
    contacts = [_ic_contact(p, i) for i, p in enumerate(PEOPLE)]
    start_idx = 0
    if starting_after:
        for i, c in enumerate(contacts):
            if c["id"] == starting_after:
                start_idx = i + 1
                break
    page = contacts[start_idx:start_idx + per_page]
    has_next = start_idx + per_page < len(contacts)
    pages = {
        "type": "pages", "page": 1, "per_page": per_page,
        "total_pages": max(1, -(-len(contacts) // per_page)),
    }
    if has_next:
        pages["next"] = {"page": 2, "starting_after": page[-1]["id"]}
    return {"type": "list", "data": page, "total_count": len(contacts), "pages": pages}


@router.get("/conversations")
async def list_conversations(request: Request, starting_after: str = Query(None), per_page: int = Query(20, ge=1, le=150)):
    _ic_auth(request)
    conversations = [_ic_conversation(t, i) for i, t in enumerate(TICKETS)]
    start_idx = 0
    if starting_after:
        for i, c in enumerate(conversations):
            if c["id"] == starting_after:
                start_idx = i + 1
                break
    page = conversations[start_idx:start_idx + per_page]
    has_next = start_idx + per_page < len(conversations)
    pages = {
        "type": "pages", "page": 1, "per_page": per_page,
        "total_pages": max(1, -(-len(conversations) // per_page)),
    }
    if has_next:
        pages["next"] = {"page": 2, "starting_after": page[-1]["id"]}
    return {"type": "conversation.list", "conversations": page, "total_count": len(conversations), "pages": pages}


@router.get("/companies")
async def list_companies(request: Request, page: int = Query(1, ge=1), per_page: int = Query(15, ge=1, le=60)):
    _ic_auth(request)
    companies = [_ic_company(c, i) for i, c in enumerate(COMPANIES)]
    offset = (page - 1) * per_page
    page_items = companies[offset:offset + per_page]
    total_pages = max(1, -(-len(companies) // per_page))
    pages = {"type": "pages", "page": page, "per_page": per_page, "total_pages": total_pages}
    if page < total_pages:
        pages["next"] = {"page": page + 1, "starting_after": page_items[-1]["id"] if page_items else None}
    return {"type": "list", "data": page_items, "total_count": len(companies), "pages": pages}


@router.get("/contacts/{contact_id}/notes")
async def contact_notes(request: Request, contact_id: str, page: int = Query(1), per_page: int = Query(10)):
    _ic_auth(request)
    notes = [
        {
            "type": "note", "id": f"note_{contact_id}_001",
            "created_at": 1720195200,
            "body": "<p>VIP customer — escalate any billing issues directly to finance team.</p>",
            "author": {"type": "admin", "id": "12345", "name": "Support Agent", "email": "support@os.dev"},
            "contact": {"type": "contact", "id": contact_id},
        },
    ]
    return {
        "type": "list", "data": notes, "total_count": len(notes),
        "pages": {"type": "pages", "page": page, "per_page": per_page, "total_pages": 1},
    }
