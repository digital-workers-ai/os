"""
Twilio API mock provider.
Contract: seeds/docs/21-twilio.md

Basic Auth (AccountSID:AuthToken). Page-based pagination with PageToken.
RFC 2822 dates. SID prefixes (AC/SM/CA). Price as negative strings.
"""

from fastapi import APIRouter, Request, Query
from seeds.helpers import require_basic_auth, page_paginate
from seeds.world import PEOPLE, COMPANIES_BY_ID

router = APIRouter()

_ACCOUNT_SID = "ACmock1234567890abcdef1234567890"

_MESSAGES = [
    {
        "sid": "SMmock00000000000000000000000001",
        "date_created": "Mon, 14 Jul 2026 10:30:00 +0000",
        "date_updated": "Mon, 14 Jul 2026 10:30:02 +0000",
        "date_sent": "Mon, 14 Jul 2026 10:30:01 +0000",
        "account_sid": _ACCOUNT_SID, "to": "+14155551234", "from": "+18005551000",
        "messaging_service_sid": "MGmock00000000000000000000000001",
        "body": "Your verification code is 482910. It expires in 10 minutes.",
        "status": "delivered", "num_segments": "1", "num_media": "0",
        "direction": "outbound-api", "api_version": "2010-04-01",
        "price": "-0.0075", "price_unit": "USD",
        "error_code": None, "error_message": None,
        "uri": f"/2010-04-01/Accounts/{_ACCOUNT_SID}/Messages/SMmock00000000000000000000000001.json",
        "subresource_uris": {
            "media": f"/2010-04-01/Accounts/{_ACCOUNT_SID}/Messages/SMmock00000000000000000000000001/Media.json",
            "feedback": f"/2010-04-01/Accounts/{_ACCOUNT_SID}/Messages/SMmock00000000000000000000000001/Feedback.json",
        },
    },
    {
        "sid": "SMmock00000000000000000000000002",
        "date_created": "Mon, 14 Jul 2026 11:00:00 +0000",
        "date_updated": "Mon, 14 Jul 2026 11:00:03 +0000",
        "date_sent": "Mon, 14 Jul 2026 11:00:01 +0000",
        "account_sid": _ACCOUNT_SID, "to": "+15125550201", "from": "+18005551000",
        "messaging_service_sid": "MGmock00000000000000000000000001",
        "body": "Your order #1234 has been shipped. Track it at acme.io/track/1234",
        "status": "delivered", "num_segments": "1", "num_media": "0",
        "direction": "outbound-api", "api_version": "2010-04-01",
        "price": "-0.0075", "price_unit": "USD",
        "error_code": None, "error_message": None,
        "uri": f"/2010-04-01/Accounts/{_ACCOUNT_SID}/Messages/SMmock00000000000000000000000002.json",
        "subresource_uris": {
            "media": f"/2010-04-01/Accounts/{_ACCOUNT_SID}/Messages/SMmock00000000000000000000000002/Media.json",
            "feedback": f"/2010-04-01/Accounts/{_ACCOUNT_SID}/Messages/SMmock00000000000000000000000002/Feedback.json",
        },
    },
    {
        "sid": "SMmock00000000000000000000000003",
        "date_created": "Sun, 13 Jul 2026 15:22:00 +0000",
        "date_updated": "Sun, 13 Jul 2026 15:22:04 +0000",
        "date_sent": "Sun, 13 Jul 2026 15:22:01 +0000",
        "account_sid": _ACCOUNT_SID, "to": "+13125550301", "from": "+18005551000",
        "messaging_service_sid": "MGmock00000000000000000000000001",
        "body": "Reminder: Your subscription renews tomorrow.",
        "status": "delivered", "num_segments": "1", "num_media": "0",
        "direction": "outbound-api", "api_version": "2010-04-01",
        "price": "-0.0075", "price_unit": "USD",
        "error_code": None, "error_message": None,
        "uri": f"/2010-04-01/Accounts/{_ACCOUNT_SID}/Messages/SMmock00000000000000000000000003.json",
        "subresource_uris": {
            "media": f"/2010-04-01/Accounts/{_ACCOUNT_SID}/Messages/SMmock00000000000000000000000003/Media.json",
            "feedback": f"/2010-04-01/Accounts/{_ACCOUNT_SID}/Messages/SMmock00000000000000000000000003/Feedback.json",
        },
    },
]

_CALLS = [
    {
        "sid": "CAmock00000000000000000000000001",
        "date_created": "Mon, 14 Jul 2026 14:00:00 +0000",
        "date_updated": "Mon, 14 Jul 2026 14:05:30 +0000",
        "parent_call_sid": None, "annotation": None, "answered_by": "human",
        "account_sid": _ACCOUNT_SID, "to": "+14155551234", "to_formatted": "(415) 555-1234",
        "from": "+18005551000", "from_formatted": "(800) 555-1000",
        "caller_name": "ACME CORP",
        "phone_number_sid": "PNmock00000000000000000000000001",
        "status": "completed", "start_time": "Mon, 14 Jul 2026 14:00:05 +0000",
        "end_time": "Mon, 14 Jul 2026 14:05:30 +0000",
        "duration": "325", "direction": "outbound-api", "api_version": "2010-04-01",
        "forwarded_from": None, "group_sid": None, "trunk_sid": None, "queue_time": "0",
        "price": "-0.0130", "price_unit": "USD",
        "uri": f"/2010-04-01/Accounts/{_ACCOUNT_SID}/Calls/CAmock00000000000000000000000001.json",
        "subresource_uris": {
            "notifications": f"/2010-04-01/Accounts/{_ACCOUNT_SID}/Calls/CAmock00000000000000000000000001/Notifications.json",
            "recordings": f"/2010-04-01/Accounts/{_ACCOUNT_SID}/Calls/CAmock00000000000000000000000001/Recordings.json",
            "feedback": f"/2010-04-01/Accounts/{_ACCOUNT_SID}/Calls/CAmock00000000000000000000000001/Feedback.json",
        },
    },
    {
        "sid": "CAmock00000000000000000000000002",
        "date_created": "Mon, 14 Jul 2026 09:15:00 +0000",
        "date_updated": "Mon, 14 Jul 2026 09:18:45 +0000",
        "parent_call_sid": None, "annotation": None, "answered_by": "human",
        "account_sid": _ACCOUNT_SID, "to": "+15125550201", "to_formatted": "(512) 555-0201",
        "from": "+18005551000", "from_formatted": "(800) 555-1000",
        "caller_name": "ACME CORP",
        "phone_number_sid": "PNmock00000000000000000000000001",
        "status": "completed", "start_time": "Mon, 14 Jul 2026 09:15:03 +0000",
        "end_time": "Mon, 14 Jul 2026 09:18:45 +0000",
        "duration": "222", "direction": "outbound-api", "api_version": "2010-04-01",
        "forwarded_from": None, "group_sid": None, "trunk_sid": None, "queue_time": "0",
        "price": "-0.0130", "price_unit": "USD",
        "uri": f"/2010-04-01/Accounts/{_ACCOUNT_SID}/Calls/CAmock00000000000000000000000002.json",
        "subresource_uris": {
            "notifications": f"/2010-04-01/Accounts/{_ACCOUNT_SID}/Calls/CAmock00000000000000000000000002/Notifications.json",
            "recordings": f"/2010-04-01/Accounts/{_ACCOUNT_SID}/Calls/CAmock00000000000000000000000002/Recordings.json",
            "feedback": f"/2010-04-01/Accounts/{_ACCOUNT_SID}/Calls/CAmock00000000000000000000000002/Feedback.json",
        },
    },
]


@router.get("/2010-04-01/Accounts/{account_sid}/Messages.json")
async def list_messages(
    request: Request,
    account_sid: str,
    PageSize: int = Query(50, ge=1, le=1000),
    Page: int = Query(0),
    PageToken: str = Query(None),
):
    require_basic_auth(request)
    page_items, total = page_paginate(_MESSAGES, Page, PageSize)
    base = f"/2010-04-01/Accounts/{account_sid}/Messages.json"
    has_next = (Page + 1) * PageSize < total
    next_token = f"PASM{Page+1:04d}" if has_next else None
    next_uri = f"{base}?PageSize={PageSize}&Page={Page+1}&PageToken={next_token}" if has_next else None
    return {
        "first_page_uri": f"{base}?PageSize={PageSize}&Page=0",
        "end": min((Page + 1) * PageSize, total) - 1,
        "previous_page_uri": f"{base}?PageSize={PageSize}&Page={Page-1}" if Page > 0 else None,
        "messages": page_items,
        "uri": f"{base}?PageSize={PageSize}&Page={Page}",
        "page_size": PageSize, "start": Page * PageSize, "page": Page,
        "next_page_uri": next_uri,
    }


@router.get("/2010-04-01/Accounts/{account_sid}/Calls.json")
async def list_calls(
    request: Request,
    account_sid: str,
    PageSize: int = Query(50, ge=1, le=1000),
    Page: int = Query(0),
    PageToken: str = Query(None),
):
    require_basic_auth(request)
    page_items, total = page_paginate(_CALLS, Page, PageSize)
    base = f"/2010-04-01/Accounts/{account_sid}/Calls.json"
    has_next = (Page + 1) * PageSize < total
    next_token = f"PACA{Page+1:04d}" if has_next else None
    next_uri = f"{base}?PageSize={PageSize}&Page={Page+1}&PageToken={next_token}" if has_next else None
    return {
        "first_page_uri": f"{base}?PageSize={PageSize}&Page=0",
        "end": min((Page + 1) * PageSize, total) - 1,
        "previous_page_uri": f"{base}?PageSize={PageSize}&Page={Page-1}" if Page > 0 else None,
        "calls": page_items,
        "uri": f"{base}?PageSize={PageSize}&Page={Page}",
        "page_size": PageSize, "start": Page * PageSize, "page": Page,
        "next_page_uri": next_uri,
    }


@router.get("/2010-04-01/Accounts/{account_sid}.json")
async def get_account(request: Request, account_sid: str):
    require_basic_auth(request)
    return {
        "sid": account_sid,
        "friendly_name": "Acme Corp Production",
        "type": "Full",
        "status": "active",
        "date_created": "Wed, 15 Jan 2025 10:00:00 +0000",
        "date_updated": "Mon, 14 Jul 2026 08:00:00 +0000",
        "owner_account_sid": account_sid,
        "auth_token": "mock_auth_token_xxxxxxxxxxxx",
        "uri": f"/2010-04-01/Accounts/{account_sid}.json",
        "subresource_uris": {
            "available_phone_numbers": f"/2010-04-01/Accounts/{account_sid}/AvailablePhoneNumbers.json",
            "calls": f"/2010-04-01/Accounts/{account_sid}/Calls.json",
            "conferences": f"/2010-04-01/Accounts/{account_sid}/Conferences.json",
            "incoming_phone_numbers": f"/2010-04-01/Accounts/{account_sid}/IncomingPhoneNumbers.json",
            "messages": f"/2010-04-01/Accounts/{account_sid}/Messages.json",
            "notifications": f"/2010-04-01/Accounts/{account_sid}/Notifications.json",
            "outgoing_caller_ids": f"/2010-04-01/Accounts/{account_sid}/OutgoingCallerIds.json",
            "recordings": f"/2010-04-01/Accounts/{account_sid}/Recordings.json",
            "usage": f"/2010-04-01/Accounts/{account_sid}/Usage.json",
        },
    }
