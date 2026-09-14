from fastapi import APIRouter, Request, Query
from seeds.helpers import require_bearer, require_basic_auth, offset_paginate
from seeds.world import PEOPLE, COMPANIES_BY_ID, EMAIL_CAMPAIGNS

router = APIRouter()

_DC = "us21"
_API = f"https://{_DC}.api.mailchimp.com/3.0"
_SCHEMA = f"https://{_DC}.api.mailchimp.com/schema/3.0"

_STATUS = {"sent": "sent", "scheduled": "schedule", "draft": "save"}


def _mc_auth(request: Request):
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        require_bearer(request)
    elif auth.startswith("Basic "):
        require_basic_auth(request)
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail={"type": "https://mailchimp.com/developer/marketing/docs/errors/", "title": "API Key Missing", "status": 401, "detail": "Your request did not include an API key."})


def _mc_links(path: str, collection: str, definition: str):
    return [
        {"rel": "self", "href": f"{_API}{path}", "method": "GET", "targetSchema": f"{_SCHEMA}/Definitions/{definition}/Response.json"},
        {"rel": "parent", "href": f"{_API}{collection}", "method": "GET", "schema": f"{_SCHEMA}/Paths/{definition}/Collection.json", "targetSchema": f"{_SCHEMA}/Definitions/{definition}/CollectionResponse.json"},
        {"rel": "delete", "href": f"{_API}{path}", "method": "DELETE"},
    ]


def _mc_time(value) -> str:
    return value.replace("Z", "+00:00") if value else ""


_LISTS = [
    {
        "id": "mc_list_001", "web_id": 123456, "name": "Main Newsletter",
        "contact": {"company": "Acme Corp", "address1": "123 Main St", "address2": "", "city": "San Francisco", "state": "CA", "zip": "94105", "country": "US", "phone": "+1-415-555-0142"},
        "permission_reminder": "You signed up on our website.",
        "use_archive_bar": True,
        "campaign_defaults": {"from_name": "Acme Team", "from_email": "hello@acme.io", "subject": "", "language": "en"},
        "notify_on_subscribe": "", "notify_on_unsubscribe": "",
        "date_created": "2025-01-15T10:00:00+00:00", "list_rating": 4,
        "email_type_option": False,
        "subscribe_url_short": "http://eepurl.com/mock-main",
        "subscribe_url_long": f"https://acme.{_DC}.list-manage.com/subscribe?u=mock&id=mc_list_001",
        "beamer_address": f"{_DC}-mock-1@inbound.mailchimp.com",
        "visibility": "pub", "double_optin": False, "has_welcome": True,
        "marketing_permissions": False, "modules": [],
        "stats": {
            "member_count": 4500, "unsubscribe_count": 120, "cleaned_count": 45,
            "member_count_since_send": 180, "unsubscribe_count_since_send": 6, "cleaned_count_since_send": 2,
            "campaign_count": 8, "campaign_last_sent": "2026-07-10T14:00:00+00:00",
            "merge_field_count": 4, "avg_sub_rate": 120, "avg_unsub_rate": 5, "target_sub_rate": 40,
            "open_rate": 0.42, "click_rate": 0.076,
            "last_sub_date": "2026-07-14T09:15:00+00:00", "last_unsub_date": "2026-07-12T16:30:00+00:00",
        },
        "_links": _mc_links("/lists/mc_list_001", "/lists", "Lists"),
    },
    {
        "id": "mc_list_002", "web_id": 123457, "name": "Product Updates",
        "contact": {"company": "Acme Corp", "address1": "123 Main St", "address2": "Suite 400", "city": "San Francisco", "state": "CA", "zip": "94105", "country": "US", "phone": ""},
        "permission_reminder": "You opted in for product updates.",
        "use_archive_bar": False,
        "campaign_defaults": {"from_name": "Acme Product", "from_email": "product@acme.io", "subject": "", "language": "en"},
        "notify_on_subscribe": "", "notify_on_unsubscribe": "ops@acme.io",
        "date_created": "2025-06-01T08:00:00+00:00", "list_rating": 3,
        "email_type_option": False,
        "subscribe_url_short": "http://eepurl.com/mock-updates",
        "subscribe_url_long": f"https://acme.{_DC}.list-manage.com/subscribe?u=mock&id=mc_list_002",
        "beamer_address": f"{_DC}-mock-2@inbound.mailchimp.com",
        "visibility": "prv", "double_optin": True, "has_welcome": False,
        "marketing_permissions": False, "modules": [],
        "stats": {
            "member_count": 2100, "unsubscribe_count": 35, "cleaned_count": 12,
            "member_count_since_send": 64, "unsubscribe_count_since_send": 0, "cleaned_count_since_send": 0,
            "campaign_count": 4, "campaign_last_sent": "2026-06-25T11:00:00+00:00",
            "merge_field_count": 2, "avg_sub_rate": 45, "avg_unsub_rate": 2, "target_sub_rate": 20,
            "open_rate": 0.38, "click_rate": 0.065,
            "last_sub_date": "2026-07-11T18:40:00+00:00", "last_unsub_date": "",
        },
        "_links": _mc_links("/lists/mc_list_002", "/lists", "Lists"),
    },
]


def _mc_member(p):
    co = COMPANIES_BY_ID.get(p.company_id)
    return {
        "id": f"mc_mem_{p.id}", "email_address": p.email,
        "unique_email_id": f"uid_{p.id}", "contact_id": f"mc_contact_{p.id}",
        "full_name": f"{p.first_name} {p.last_name}",
        "status": "subscribed", "email_type": "html",
        "merge_fields": {"FNAME": p.first_name, "LNAME": p.last_name, "COMPANY": co.name if co else ""},
        "stats": {"avg_open_rate": 0.45, "avg_click_rate": 0.08},
        "timestamp_signup": f"{p.created_at}T00:00:00+00:00",
        "timestamp_opt": f"{p.created_at}T00:00:00+00:00",
        "last_changed": f"{p.last_seen}T00:00:00+00:00" if p.last_seen else f"{p.created_at}T00:00:00+00:00",
        "list_id": "mc_list_001",
        "tags": [{"id": 1, "name": "customer"}],
        "_links": [],
    }


def _mc_campaign(ec):
    send_time = _mc_time(ec.sent_at)
    campaign = {
        "id": f"mc_camp_{ec.id}", "web_id": int(ec.id.replace("ec", "900")),
        "type": "regular", "create_time": "2026-06-20T10:00:00+00:00",
        "archive_url": f"https://mailchi.mp/mock/{ec.id}",
        "long_archive_url": f"https://{_DC}.campaign-archive.com/?u=mock&id={ec.id}",
        "status": _STATUS.get(ec.status, "save"),
        "emails_sent": ec.sends, "send_time": send_time,
        "content_type": "template",
        "needs_block_refresh": False, "resendable": bool(send_time),
        "recipients": {"list_id": "mc_list_001", "list_is_active": True, "list_name": "Main Newsletter", "segment_text": "", "recipient_count": ec.sends or 4500},
        "settings": {
            "subject_line": ec.subject, "preview_text": "", "title": ec.name,
            "from_name": "Acme Team", "reply_to": "hello@acme.io",
            "use_conversation": False, "to_name": "*|FNAME|*", "folder_id": "",
            "authenticate": True, "auto_footer": True, "inline_css": False,
            "auto_tweet": False, "fb_comments": False, "timewarp": False,
            "template_id": 12345, "drag_and_drop": True,
        },
        "tracking": {"opens": True, "html_clicks": True, "text_clicks": False, "goal_tracking": False, "ecomm360": False, "google_analytics": "", "clicktale": ""},
        "delivery_status": {"enabled": False},
        "_links": _mc_links(f"/campaigns/mc_camp_{ec.id}", "/campaigns", "Campaigns"),
    }
    if send_time:
        campaign["report_summary"] = {
            "opens": ec.opens, "unique_opens": int(ec.opens * 0.85),
            "open_rate": ec.opens / ec.sends,
            "clicks": ec.clicks, "subscriber_clicks": int(ec.clicks * 0.9),
            "click_rate": ec.clicks / ec.sends,
            "ecommerce": {"total_orders": 0, "total_spent": 0, "total_revenue": 0},
        }
    return campaign


@router.get("/3.0/lists")
async def list_lists(request: Request, count: int = Query(10), offset: int = Query(0)):
    _mc_auth(request)
    page, total = offset_paginate(_LISTS, offset, count)
    return {
        "lists": page,
        "total_items": total,
        "constraints": {"may_create": True, "max_instances": 500, "current_total_instances": total},
        "_links": [{"rel": "self", "href": f"{_API}/lists", "method": "GET"}],
    }


@router.get("/3.0/lists/{list_id}/members")
async def list_members(request: Request, list_id: str, count: int = Query(10), offset: int = Query(0)):
    _mc_auth(request)
    members = [_mc_member(p) for p in PEOPLE[:10]]
    page, total = offset_paginate(members, offset, count)
    return {"members": page, "list_id": list_id, "total_items": total, "_links": []}


@router.get("/3.0/campaigns")
async def list_campaigns(request: Request, count: int = Query(10), offset: int = Query(0), status: str = Query(None)):
    _mc_auth(request)
    campaigns = [_mc_campaign(ec) for ec in EMAIL_CAMPAIGNS]
    if status:
        campaigns = [c for c in campaigns if c["status"] == status]
    page, total = offset_paginate(campaigns, offset, count)
    return {
        "campaigns": page,
        "total_items": total,
        "_links": [{"rel": "self", "href": f"{_API}/campaigns", "method": "GET"}],
    }


@router.get("/3.0/reports/{campaign_id}")
async def campaign_report(request: Request, campaign_id: str):
    _mc_auth(request)
    cid = campaign_id.replace("mc_camp_", "")
    ec = next((e for e in EMAIL_CAMPAIGNS if e.id == cid), EMAIL_CAMPAIGNS[0])
    return {
        "id": campaign_id, "campaign_title": ec.name,
        "type": "regular", "list_id": "mc_list_001", "list_is_active": True, "list_name": "Main Newsletter",
        "subject_line": ec.subject, "emails_sent": ec.sends,
        "abuse_reports": 0, "unsubscribed": ec.unsubscribes,
        "send_time": _mc_time(ec.sent_at),
        "opens": {"opens_total": ec.opens, "unique_opens": int(ec.opens * 0.85), "open_rate": ec.opens / ec.sends if ec.sends else 0},
        "clicks": {"clicks_total": ec.clicks, "unique_clicks": int(ec.clicks * 0.9), "unique_subscriber_clicks": int(ec.clicks * 0.85), "click_rate": ec.clicks / ec.sends if ec.sends else 0},
        "bounces": {"hard_bounces": int(ec.bounces * 0.3), "soft_bounces": int(ec.bounces * 0.7), "syntax_errors": 0},
        "delivery_status": {"enabled": False},
        "_links": [],
    }
