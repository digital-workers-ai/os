"""
Shared auth decorators and pagination helpers for the mock server.
"""

import base64
import hashlib
from datetime import date, timedelta
from functools import wraps
from typing import Any, Optional

from fastapi import Request, HTTPException


# --- Auth Decorators ---

def require_bearer(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer ") or len(auth) <= 7:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return auth[7:]


def require_basic_auth(request: Request) -> tuple[str, str]:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Basic ") or len(auth) <= 6:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        decoded = base64.b64decode(auth[6:]).decode()
        username, _, password = decoded.partition(":")
        return username, password
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")


def require_query_token(request: Request, param: str = "access_token") -> str:
    token = request.query_params.get(param, "")
    if not token:
        raise HTTPException(
            status_code=400,
            detail={"error": {"message": f"An access token is required to request this resource.", "type": "OAuthException", "code": 190}},
        )
    return token


def require_header(request: Request, header: str) -> str:
    value = request.headers.get(header, "")
    if not value:
        raise HTTPException(status_code=401, detail=f"Missing required header: {header}")
    return value


# --- Pagination Helpers ---

def cursor_paginate(
    items: list,
    after: Optional[str],
    limit: int,
    id_field: str = "id",
) -> tuple[list, Optional[str]]:
    """HubSpot/Stripe/Customer.io/LinkedIn style cursor pagination.
    Returns (page_items, next_cursor_or_none).
    """
    start_idx = 0
    if after:
        for i, item in enumerate(items):
            item_id = item[id_field] if isinstance(item, dict) else getattr(item, id_field)
            if str(item_id) == str(after):
                start_idx = i + 1
                break

    page = items[start_idx : start_idx + limit]
    next_cursor = None
    if start_idx + limit < len(items):
        last = page[-1]
        next_cursor = str(last[id_field] if isinstance(last, dict) else getattr(last, id_field))

    return page, next_cursor


def offset_paginate(
    items: list,
    offset: int,
    limit: int,
) -> tuple[list, int]:
    """Mailchimp/ActiveCampaign style offset pagination.
    Returns (page_items, total_count).
    """
    page = items[offset : offset + limit]
    return page, len(items)


def token_paginate(
    items: list,
    page_token: Optional[str],
    page_size: int,
) -> tuple[list, Optional[str]]:
    """GA4/Calendly style token pagination.
    Token encodes the offset. Returns (page_items, next_token_or_none).
    """
    offset = 0
    if page_token:
        try:
            offset = int(base64.b64decode(page_token).decode())
        except Exception:
            offset = 0

    page = items[offset : offset + page_size]
    next_token = None
    if offset + page_size < len(items):
        next_offset = offset + page_size
        next_token = base64.b64encode(str(next_offset).encode()).decode()

    return page, next_token


def bookmark_paginate(
    items: list,
    bookmark: Optional[str],
    page_size: int,
) -> tuple[list, Optional[str]]:
    """Pinterest style bookmark pagination.
    Returns (page_items, next_bookmark_or_none).
    """
    offset = 0
    if bookmark:
        try:
            offset = int(base64.b64decode(bookmark).decode())
        except Exception:
            offset = 0

    page = items[offset : offset + page_size]
    next_bookmark = None
    if offset + page_size < len(items):
        next_offset = offset + page_size
        next_bookmark = base64.b64encode(str(next_offset).encode()).decode()

    return page, next_bookmark


def page_paginate(
    items: list,
    page: int,
    page_size: int,
) -> tuple[list, int]:
    """Twilio/WooCommerce style page-number pagination.
    Returns (page_items, total_count).
    """
    offset = page * page_size
    page_items = items[offset : offset + page_size]
    return page_items, len(items)


def session_paginate(
    items: list,
    session_id: Optional[str],
    page: int,
    page_size: int,
) -> tuple[list, str, int]:
    """Mixpanel engage style session-based pagination.
    Returns (page_items, session_id, total).
    """
    if not session_id:
        session_id = hashlib.md5(str(len(items)).encode()).hexdigest()[:12]

    offset = page * page_size
    page_items = items[offset : offset + page_size]
    return page_items, session_id, len(items)


def link_header_paginate(
    items: list,
    page_info: Optional[str],
    limit: int,
    base_url: str,
) -> tuple[list, dict[str, str]]:
    """Shopify style Link header cursor pagination.
    Returns (page_items, link_headers_dict).
    """
    offset = 0
    if page_info:
        try:
            offset = int(base64.b64decode(page_info).decode())
        except Exception:
            offset = 0

    page = items[offset : offset + limit]
    links = {}

    if offset + limit < len(items):
        next_offset = offset + limit
        next_info = base64.b64encode(str(next_offset).encode()).decode()
        links["next"] = f'<{base_url}?page_info={next_info}&limit={limit}>; rel="next"'

    if offset > 0:
        prev_offset = max(0, offset - limit)
        prev_info = base64.b64encode(str(prev_offset).encode()).decode()
        links["previous"] = f'<{base_url}?page_info={prev_info}&limit={limit}>; rel="previous"'

    return page, links


def day_factor(day: date) -> float:
    weekday = 0.6 if day.weekday() >= 5 else 1.0
    sawtooth = 0.8 + 0.4 * ((day.day - 1) % 10) / 9
    return weekday * sawtooth


def days_between(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def campaign_days(ac, since: date, until: date) -> list[date]:
    start = max(since, date.fromisoformat(ac.start_date))
    end = min(until, date.fromisoformat(ac.end_date)) if ac.end_date else until
    return days_between(start, end)


def daily_share(total: int, ac, day: date, until: date) -> int:
    days_run = (until - date.fromisoformat(ac.start_date)).days + 1
    return round(total * day_factor(day) / days_run)
