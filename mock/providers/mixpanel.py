"""
Mixpanel API mock provider.
Contract: seeds/docs/24-mixpanel.md

Basic Auth. NDJSON export. Session-based engage pagination.
"""

from fastapi import APIRouter, Request, Query
from fastapi.responses import PlainTextResponse
from seeds.helpers import require_basic_auth, session_paginate
from seeds.world import PEOPLE, COMPANIES_BY_ID, ANALYTICS_EVENTS
import json

router = APIRouter()


def _mp_event(ev):
    p = next((pp for pp in PEOPLE if pp.email == ev.distinct_id), None)
    co = COMPANIES_BY_ID.get(p.company_id) if p else None
    props = {
        "time": 1720454400,
        "distinct_id": f"user_{p.first_name.lower()}_{co.domain.split('.')[0]}" if p and co else ev.distinct_id,
        "$insert_id": f"mp_{ev.id}",
        "$browser": "Chrome", "$city": co.city if co else "San Francisco",
        "$region": co.state if co else "CA", "$country_code": "US",
        "$os": "Mac OS X", "mp_lib": "web",
        "$current_url": f"https://app.acme.io{ev.properties.get('page', '/')}",
    }
    props.update(ev.properties)
    return {"event": ev.event, "properties": props}


def _mp_profile(p):
    co = COMPANIES_BY_ID.get(p.company_id)
    sub = None
    if co:
        from seeds.world import SUBSCRIPTIONS_BY_COMPANY
        sub = SUBSCRIPTIONS_BY_COMPANY.get(co.id)
    return {
        "$distinct_id": f"user_{p.first_name.lower()}_{co.domain.split('.')[0]}" if co else f"user_{p.id}",
        "$properties": {
            "$email": p.email,
            "$first_name": p.first_name, "$last_name": p.last_name,
            "$name": f"{p.first_name} {p.last_name}",
            "$created": f"{p.created_at}T00:00:00",
            "$last_seen": f"{p.last_seen}T00:00:00" if p.last_seen else None,
            "$browser": "Chrome", "$city": co.city if co else None,
            "$region": co.state if co else None, "$country_code": "US",
            "plan": sub.plan if sub else "free",
            "company": co.name if co else "",
            "company_domain": co.domain if co else "",
        },
    }


@router.get("/api/2.0/export")
async def export_events(
    request: Request,
    project_id: int = Query(None),
    from_date: str = Query(...),
    to_date: str = Query(...),
    event: str = Query(None),
):
    require_basic_auth(request)
    events = [_mp_event(ev) for ev in ANALYTICS_EVENTS]
    if event:
        try:
            names = json.loads(event)
            events = [e for e in events if e["event"] in names]
        except (json.JSONDecodeError, TypeError):
            pass
    lines = [json.dumps(e) for e in events]
    return PlainTextResponse("\n".join(lines), media_type="application/x-ndjson")


@router.post("/api/query/engage")
async def engage_profiles(request: Request):
    require_basic_auth(request)
    body = {}
    content_type = request.headers.get("content-type", "")
    if "json" in content_type:
        body = await request.json()
    elif "form" in content_type:
        form = await request.form()
        body = dict(form)
    session_id = body.get("session_id") or request.query_params.get("session_id")
    page = int(body.get("page", request.query_params.get("page", 0)))
    profiles = [_mp_profile(p) for p in PEOPLE]
    page_items, sid, total = session_paginate(profiles, session_id, page, 1000)
    return {
        "page": page, "page_size": 1000,
        "results": page_items,
        "session_id": sid,
        "status": "ok",
        "total": total,
    }


@router.get("/api/query/insights")
async def insights(
    request: Request,
    project_id: int = Query(None),
    bookmark_id: int = Query(None),
):
    require_basic_auth(request)
    return {
        "computed_at": "2026-07-14T23:59:59.000Z",
        "date_range": {"from_date": "2026-07-08", "to_date": "2026-07-14"},
        "headers": ["$overall"],
        "series": {
            "page_view": {"2026-07-08": 142, "2026-07-09": 138, "2026-07-10": 155, "2026-07-11": 131, "2026-07-12": 148, "2026-07-13": 152, "2026-07-14": 145},
            "feature_used": {"2026-07-08": 42, "2026-07-09": 38, "2026-07-10": 55, "2026-07-11": 31, "2026-07-12": 48, "2026-07-13": 52, "2026-07-14": 45},
        },
    }
