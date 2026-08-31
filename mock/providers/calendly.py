"""
Calendly API v2 mock provider.
Contract: seeds/docs/10-calendly.md

Bearer auth. Token pagination via page_token/next_page_token.
"""

from fastapi import APIRouter, Request, Query
from seeds.helpers import require_bearer, token_paginate
from seeds.world import PEOPLE, COMPANIES_BY_ID

router = APIRouter()

_USER_URI = "https://api.calendly.com/users/abc123def456"
_ORG_URI = "https://api.calendly.com/organizations/org789"

_EVENTS = [
    {
        "uri": "https://api.calendly.com/scheduled_events/evt_001",
        "name": "30 Minute Demo",
        "status": "active",
        "start_time": "2026-06-05T14:00:00.000000Z",
        "end_time": "2026-06-05T14:30:00.000000Z",
        "event_type": "https://api.calendly.com/event_types/et_demo30",
        "location": {"type": "google_conference", "join_url": "https://meet.google.com/abc-defg-hij", "status": "pushed"},
        "invitees_counter": {"total": 1, "active": 1, "limit": 1},
        "created_at": "2026-06-03T09:15:00.000000Z",
        "updated_at": "2026-06-03T09:15:00.000000Z",
        "event_memberships": [{"user": _USER_URI, "user_email": "jane@acme.io", "user_name": "Jane Smith"}],
        "calendar_event": {"kind": "google", "external_id": "google_cal_abc123"},
    },
    {
        "uri": "https://api.calendly.com/scheduled_events/evt_002",
        "name": "Discovery Call",
        "status": "active",
        "start_time": "2026-06-10T16:00:00.000000Z",
        "end_time": "2026-06-10T16:45:00.000000Z",
        "event_type": "https://api.calendly.com/event_types/et_discovery",
        "location": {"type": "zoom", "join_url": "https://zoom.us/j/123456789", "status": "pushed"},
        "invitees_counter": {"total": 2, "active": 2, "limit": 5},
        "created_at": "2026-06-08T11:30:00.000000Z",
        "updated_at": "2026-06-08T11:30:00.000000Z",
        "event_memberships": [{"user": _USER_URI, "user_email": "jane@acme.io", "user_name": "Jane Smith"}],
        "calendar_event": {"kind": "google", "external_id": "google_cal_def456"},
    },
    {
        "uri": "https://api.calendly.com/scheduled_events/evt_003",
        "name": "30 Minute Demo",
        "status": "canceled",
        "start_time": "2026-06-15T10:00:00.000000Z",
        "end_time": "2026-06-15T10:30:00.000000Z",
        "event_type": "https://api.calendly.com/event_types/et_demo30",
        "location": {"type": "google_conference", "join_url": "https://meet.google.com/xyz-uvwx-rst", "status": "pushed"},
        "invitees_counter": {"total": 1, "active": 0, "limit": 1},
        "created_at": "2026-06-12T08:45:00.000000Z",
        "updated_at": "2026-06-14T16:00:00.000000Z",
        "cancellation": {"canceled_by": "Invitee", "reason": "Schedule conflict"},
        "event_memberships": [{"user": _USER_URI, "user_email": "jane@acme.io", "user_name": "Jane Smith"}],
        "calendar_event": {"kind": "google", "external_id": "google_cal_ghi789"},
    },
    {
        "uri": "https://api.calendly.com/scheduled_events/evt_004",
        "name": "Product Walkthrough",
        "status": "active",
        "start_time": "2026-06-20T11:00:00.000000Z",
        "end_time": "2026-06-20T11:45:00.000000Z",
        "event_type": "https://api.calendly.com/event_types/et_walkthrough",
        "location": {"type": "zoom", "join_url": "https://zoom.us/j/987654321", "status": "pushed"},
        "invitees_counter": {"total": 1, "active": 1, "limit": 1},
        "created_at": "2026-06-18T14:00:00.000000Z",
        "updated_at": "2026-06-18T14:00:00.000000Z",
        "event_memberships": [{"user": _USER_URI, "user_email": "jane@acme.io", "user_name": "Jane Smith"}],
        "calendar_event": {"kind": "google", "external_id": "google_cal_jkl012"},
    },
    {
        "uri": "https://api.calendly.com/scheduled_events/evt_005",
        "name": "Quarterly Review",
        "status": "active",
        "start_time": "2026-07-01T15:00:00.000000Z",
        "end_time": "2026-07-01T16:00:00.000000Z",
        "event_type": "https://api.calendly.com/event_types/et_review",
        "location": {"type": "google_conference", "join_url": "https://meet.google.com/mno-pqrs-tuv", "status": "pushed"},
        "invitees_counter": {"total": 3, "active": 3, "limit": 5},
        "created_at": "2026-06-25T09:00:00.000000Z",
        "updated_at": "2026-06-25T09:00:00.000000Z",
        "event_memberships": [{"user": _USER_URI, "user_email": "jane@acme.io", "user_name": "Jane Smith"}],
        "calendar_event": {"kind": "google", "external_id": "google_cal_mno345"},
    },
]

_INVITEES = {
    "evt_001": [
        {
            "uri": "https://api.calendly.com/scheduled_events/evt_001/invitees/inv_001",
            "email": "mike@globex.com", "name": "Mike Chen", "first_name": "Mike", "last_name": "Chen",
            "status": "active", "timezone": "America/Chicago",
            "created_at": "2026-06-03T09:15:00.000000Z", "updated_at": "2026-06-03T09:15:00.000000Z",
            "event": "https://api.calendly.com/scheduled_events/evt_001",
            "questions_and_answers": [{"question": "Company name", "answer": "Globex Inc", "position": 0}],
            "tracking": {"utm_campaign": None, "utm_source": None, "utm_medium": None, "utm_term": None, "utm_content": None, "salesforce_uuid": None},
            "text_reminder_number": None, "rescheduled": False, "routing_form_submission": None, "payment": None, "no_show": None,
        },
    ],
    "evt_002": [
        {
            "uri": "https://api.calendly.com/scheduled_events/evt_002/invitees/inv_002",
            "email": "bob@soylent.co", "name": "Bob Smith", "first_name": "Bob", "last_name": "Smith",
            "status": "active", "timezone": "America/Los_Angeles",
            "created_at": "2026-06-08T11:30:00.000000Z", "updated_at": "2026-06-08T11:30:00.000000Z",
            "event": "https://api.calendly.com/scheduled_events/evt_002",
            "questions_and_answers": [
                {"question": "Company name", "answer": "Soylent Corp", "position": 0},
                {"question": "What would you like to discuss?", "answer": "Interested in the Enterprise plan", "position": 1},
            ],
            "tracking": {"utm_campaign": "summer_promo", "utm_source": "linkedin", "utm_medium": "paid_social", "utm_term": None, "utm_content": None, "salesforce_uuid": None},
            "text_reminder_number": None, "rescheduled": False, "routing_form_submission": None, "payment": None, "no_show": None,
        },
        {
            "uri": "https://api.calendly.com/scheduled_events/evt_002/invitees/inv_003",
            "email": "alice@soylent.co", "name": "Alice Martinez", "first_name": "Alice", "last_name": "Martinez",
            "status": "active", "timezone": "America/Los_Angeles",
            "created_at": "2026-06-08T12:00:00.000000Z", "updated_at": "2026-06-08T12:00:00.000000Z",
            "event": "https://api.calendly.com/scheduled_events/evt_002",
            "questions_and_answers": [],
            "tracking": {"utm_campaign": None, "utm_source": None, "utm_medium": None, "utm_term": None, "utm_content": None, "salesforce_uuid": None},
            "text_reminder_number": None, "rescheduled": False, "routing_form_submission": None, "payment": None, "no_show": None,
        },
    ],
    "evt_003": [
        {
            "uri": "https://api.calendly.com/scheduled_events/evt_003/invitees/inv_004",
            "email": "tom@initech.io", "name": "Tom Williams", "first_name": "Tom", "last_name": "Williams",
            "status": "canceled", "timezone": "America/Chicago",
            "created_at": "2026-06-12T08:45:00.000000Z", "updated_at": "2026-06-14T16:00:00.000000Z",
            "event": "https://api.calendly.com/scheduled_events/evt_003",
            "questions_and_answers": [{"question": "Company name", "answer": "Initech LLC", "position": 0}],
            "tracking": {"utm_campaign": None, "utm_source": None, "utm_medium": None, "utm_term": None, "utm_content": None, "salesforce_uuid": None},
            "text_reminder_number": None, "rescheduled": False, "routing_form_submission": None, "payment": None, "no_show": None,
            "cancellation": {"canceled_by": "Invitee", "reason": "Schedule conflict"},
        },
    ],
}


@router.get("/users/me")
async def users_me(request: Request):
    require_bearer(request)
    return {
        "resource": {
            "uri": _USER_URI,
            "name": "Jane Smith",
            "slug": "jane-smith",
            "email": "jane@acme.io",
            "scheduling_url": "https://calendly.com/jane-smith",
            "timezone": "America/New_York",
            "avatar_url": None,
            "created_at": "2025-01-15T10:30:00.000000Z",
            "updated_at": "2026-06-01T14:22:00.000000Z",
            "current_organization": _ORG_URI,
        }
    }


@router.get("/scheduled_events")
async def list_events(
    request: Request,
    user: str = Query(None),
    organization: str = Query(None),
    count: int = Query(20, ge=1, le=100),
    sort: str = Query("start_time:asc"),
    min_start_time: str = Query(None),
    max_start_time: str = Query(None),
    status: str = Query(None),
    invitee_email: str = Query(None),
    page_token: str = Query(None),
):
    require_bearer(request)

    events = list(_EVENTS)

    if status:
        events = [e for e in events if e["status"] == status]

    page, next_token = token_paginate(events, page_token, count)

    pagination = {
        "count": len(page),
        "next_page": f"https://api.calendly.com/scheduled_events?count={count}&page_token={next_token}" if next_token else None,
        "next_page_token": next_token,
        "previous_page": None,
        "previous_page_token": None,
    }

    return {"collection": page, "pagination": pagination}


@router.get("/scheduled_events/{event_uuid}/invitees")
async def list_invitees(
    request: Request,
    event_uuid: str,
    count: int = Query(10, ge=1, le=100),
    page_token: str = Query(None),
    status: str = Query(None),
):
    require_bearer(request)

    invitees = _INVITEES.get(event_uuid, [])

    if status:
        invitees = [inv for inv in invitees if inv["status"] == status]

    page, next_token = token_paginate(invitees, page_token, count)

    pagination = {
        "count": len(page),
        "next_page": f"https://api.calendly.com/scheduled_events/{event_uuid}/invitees?count={count}&page_token={next_token}" if next_token else None,
        "next_page_token": next_token,
        "previous_page": None,
        "previous_page_token": None,
    }

    return {"collection": page, "pagination": pagination}
