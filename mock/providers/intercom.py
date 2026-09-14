"""
Intercom API v2.10 mock provider.
Contract: seeds/docs/27-intercom.md

Bearer + Intercom-Version header. Cursor pagination (starting_after).
Unix timestamps. Nested type/list structures.

Contacts carry every key a live workspace returns; the ones a workspace
only fills from the Messenger (browser, os, location, utm) come back null.
Conversations come in two shapes: Messenger-originated ones have no source
part, no title and no statistics durations, email-originated ones have all
three.
"""

from fastapi import APIRouter, Request, Query
from seeds.helpers import require_bearer, require_header
from seeds.world import PEOPLE, COMPANIES, COMPANIES_BY_ID, TICKETS, SUBSCRIPTIONS_BY_COMPANY

router = APIRouter()

MESSENGER_CONVERSATIONS = {"t1", "t2", "t3", "t4"}

CONVERSATION_ATTRIBUTES = {
    "Auto-translated": False,
    "Copilot used": False,
    "Fin AI Agent: Image used in reply": False,
    "Fin AI Agent: Preview": False,
    "Fin awaiting teammate input": False,
    "Has attachments": False,
    "Imported via standalone": False,
    "SDR Success Counted": False,
}


def _ic_auth(request: Request):
    require_bearer(request)
    require_header(request, "intercom-version")


def _ic_external_id(p, co):
    if p is None:
        return ""
    if co is None:
        return f"user_{p.id}"
    return f"user_{p.first_name.lower()}_{co.domain.split('.')[0]}"


def _ic_mini_list(contact_id, path, data=None):
    items = data or []
    return {
        "type": "list", "data": items,
        "url": f"/contacts/{contact_id}/{path}",
        "total_count": len(items), "has_more": False,
    }


def _ic_contact(p, idx):
    co = COMPANIES_BY_ID.get(p.company_id)
    contact_id = f"con_{p.id}"
    created_at = 1710500000 + idx * 86400
    companies = [
        {"type": "company", "id": f"comp_{co.id}", "url": f"/companies/comp_{co.id}"}
    ] if co else []
    return {
        "type": "contact", "id": contact_id,
        "workspace_id": "ws_mock_001",
        "external_id": _ic_external_id(p, co),
        "role": "user", "email": p.email, "phone": p.phone,
        "name": f"{p.first_name} {p.last_name}",
        "avatar": None, "owner_id": None,
        "social_profiles": {"type": "list", "data": []},
        "has_hard_bounced": False, "marked_email_as_spam": False,
        "unsubscribed_from_emails": False, "unsubscribed_from_sms": False,
        "sms_consent": False,
        "created_at": created_at,
        "updated_at": 1720454400,
        "signed_up_at": created_at,
        "last_seen_at": 1720454400,
        "last_replied_at": None, "last_contacted_at": None,
        "last_email_opened_at": None, "last_email_clicked_at": None,
        "language_override": None,
        "browser": None, "browser_version": None, "browser_language": None,
        "os": None, "referrer": None,
        "location": {
            "type": "location",
            "country": None, "region": None, "city": None,
            "country_code": None, "continent_code": None,
        },
        "android_app_name": None, "android_app_version": None,
        "android_device": None, "android_os_version": None,
        "android_sdk_version": None, "android_last_seen_at": None,
        "ios_app_name": None, "ios_app_version": None,
        "ios_device": None, "ios_os_version": None,
        "ios_sdk_version": None, "ios_last_seen_at": None,
        "utm_campaign": None, "utm_content": None, "utm_medium": None,
        "utm_source": None, "utm_term": None,
        "custom_attributes": {},
        "tags": _ic_mini_list(contact_id, "tags"),
        "notes": _ic_mini_list(contact_id, "notes"),
        "opted_in_subscription_types": _ic_mini_list(contact_id, "subscriptions"),
        "opted_out_subscription_types": _ic_mini_list(contact_id, "subscriptions"),
        "companies": _ic_mini_list(contact_id, "companies", companies),
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


def _ic_statistics(messenger, created_at):
    if messenger:
        return {
            "type": "conversation_statistics",
            "time_to_assignment": None, "time_to_admin_reply": None,
            "time_to_first_close": None, "time_to_last_close": None,
            "median_time_to_reply": None,
            "first_contact_reply_at": None, "first_assignment_at": None,
            "first_admin_reply_at": None, "first_close_at": None,
            "last_assignment_at": None, "last_assignment_admin_reply_at": None,
            "last_admin_reply_at": None, "last_close_at": None,
            "last_closed_by_id": None, "last_contact_reply_at": None,
            "count_reopens": 0, "count_assignments": 0,
            "count_conversation_parts": 2,
        }
    return {
        "type": "conversation_statistics",
        "time_to_assignment": 120, "time_to_admin_reply": 300,
        "time_to_first_close": 7200, "time_to_last_close": 7200,
        "median_time_to_reply": 300,
        "first_contact_reply_at": created_at,
        "first_assignment_at": created_at + 120,
        "first_admin_reply_at": created_at + 300,
        "first_close_at": created_at + 7200,
        "last_assignment_at": created_at + 120,
        "last_assignment_admin_reply_at": created_at + 300,
        "last_admin_reply_at": created_at + 300,
        "last_close_at": created_at + 7200,
        "last_closed_by_id": 12345,
        "last_contact_reply_at": created_at,
        "count_reopens": 0, "count_assignments": 1,
        "count_conversation_parts": 4,
    }


def _ic_source(t, p):
    return {
        "type": "conversation", "id": f"conv_{t.id}",
        "delivered_as": "customer_initiated", "subject": "",
        "body": f"<p>{t.subject}</p>",
        "author": {
            "type": "user", "id": f"con_{t.requester_id}",
            "name": f"{p.first_name} {p.last_name}" if p else "",
            "email": p.email if p else "",
        },
        "attachments": [], "url": None,
    }


def _ic_conversation(t, idx):
    p = next((pp for pp in PEOPLE if pp.id == t.requester_id), None)
    co = COMPANIES_BY_ID.get(t.company_id)
    messenger = t.id in MESSENGER_CONVERSATIONS
    created_at = 1720108800 + idx * 86400
    return {
        "type": "conversation", "id": f"conv_{t.id}",
        "created_at": created_at,
        "updated_at": 1720368000 + idx * 86400,
        "waiting_since": None, "snoozed_until": None,
        "title": None if messenger else t.subject,
        "state": "open" if t.status in ("open", "new") else "closed",
        "open": t.status in ("open", "new"),
        "read": not messenger,
        "priority": "priority" if t.priority in ("high", "urgent") else "not_priority",
        "admin_assignee_id": None if messenger else 12345,
        "team_assignee_id": None,
        "source": None if messenger else _ic_source(t, p),
        "contacts": {
            "type": "contact.list",
            "contacts": [{
                "type": "contact", "id": f"con_{t.requester_id}",
                "external_id": _ic_external_id(p, co),
            }],
        },
        "teammates": {"type": "admin.list", "admins": []},
        "first_contact_reply": None if messenger else {
            "created_at": created_at, "type": "conversation", "url": None,
        },
        "conversation_rating": None, "sla_applied": None, "ticket": None,
        "tags": {"type": "tag.list", "tags": []},
        "topics": {"type": "topic.list", "topics": [], "total_count": 0},
        "linked_objects": {
            "type": "list", "data": [], "total_count": 0, "has_more": False,
        },
        "custom_attributes": dict(CONVERSATION_ATTRIBUTES),
        "statistics": _ic_statistics(messenger, created_at),
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
