"""
Amplitude API mock provider.
Contract: seeds/docs/25-amplitude.md

Basic Auth. No pagination on any endpoint.
Export returns a zip archive of gzipped NDJSON files, one JSON object per line.
"""

PROJECT_ID = 12345

from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Query
from fastapi.responses import Response
from seeds.helpers import require_basic_auth
from seeds.world import PEOPLE, COMPANIES_BY_ID, ANALYTICS_EVENTS, SUBSCRIPTIONS_BY_COMPANY
import gzip
import io
import json
import uuid
import zipfile

router = APIRouter()

EXPORT_TIME_FORMAT = "%Y-%m-%d %H:%M:%S.%f"
INGEST_PATH = "/2/httpapi"
SECONDS_TO_UPLOAD = 2.0
SECONDS_TO_SERVER_UPLOAD = 2.007
SECONDS_TO_PROCESSED = 2.649


def _amp_time(moment, lag=0.0):
    at = datetime.fromisoformat(moment.replace("Z", "+00:00"))
    return (at + timedelta(seconds=lag)).strftime(EXPORT_TIME_FORMAT)


def _amp_event(ev, idx):
    p = next((pp for pp in PEOPLE if pp.email == ev.distinct_id), None)
    co = COMPANIES_BY_ID.get(p.company_id) if p else None
    sub = SUBSCRIPTIONS_BY_COMPANY.get(co.id) if co else None
    return {
        "event_type": ev.event,
        "event_time": _amp_time(ev.timestamp),
        "client_event_time": _amp_time(ev.timestamp),
        "client_upload_time": _amp_time(ev.timestamp, SECONDS_TO_UPLOAD),
        "server_received_time": _amp_time(ev.timestamp, SECONDS_TO_UPLOAD),
        "server_upload_time": _amp_time(ev.timestamp, SECONDS_TO_SERVER_UPLOAD),
        "processed_time": _amp_time(ev.timestamp, SECONDS_TO_PROCESSED),
        "event_id": 1000 + idx,
        "user_id": f"user_{p.first_name.lower()}_{co.domain.split('.')[0]}" if p and co else ev.distinct_id,
        "device_id": f"device_{ev.id}",
        "session_id": int(ev.properties.get("session_id", "sess_000").replace("sess_", "")) * 1000000000 + 1719835200000,
        "$insert_id": f"evt_{ev.id}",
        "$insert_key": None,
        "$schema": None,
        "uuid": str(uuid.uuid5(uuid.NAMESPACE_URL, f"amplitude/{ev.id}")),
        "event_properties": ev.properties,
        "user_properties": {
            "email": p.email if p else ev.distinct_id,
            "name": f"{p.first_name} {p.last_name}" if p else "",
            "company": co.name if co else "",
            "plan": sub.plan if sub else "free",
        },
        "global_user_properties": None,
        "group_properties": {},
        "groups": {},
        "plan": {},
        "data": {
            "group_first_event": {},
            "group_ids": {},
            "path": INGEST_PATH,
            "user_properties_updated": True,
        },
        "data_type": "event",
        "ip_address": "203.0.113.42",
        "platform": "Web", "os_name": "Mac OS X", "os_version": "14.5",
        "device_family": "Mac", "device_type": "Mac",
        "device_brand": None,
        "device_carrier": None,
        "device_manufacturer": None,
        "device_model": None,
        "language": "en-US",
        "country": "United States",
        "region": co.state if co else "CA",
        "city": co.city if co else "San Francisco",
        "dma": None,
        "location_lat": None,
        "location_lng": None,
        "adid": None,
        "idfa": None,
        "amplitude_id": 9876543210 + idx,
        "amplitude_attribution_ids": None,
        "amplitude_event_type": None,
        "is_attribution_event": None,
        "partner_id": None,
        "source_id": None,
        "sample_rate": None,
        "paying": sub is not None,
        "user_creation_time": None,
        "start_version": None,
        "version_name": None,
        "app": 12345,
        "library": "amplitude-js/8.21.0",
    }


@router.get("/api/2/export")
async def export_events(
    request: Request,
    start: str = Query(...),
    end: str = Query(...),
):
    require_basic_auth(request)
    events = [_amp_event(ev, i) for i, ev in enumerate(ANALYTICS_EVENTS)]
    lines = "\n".join(json.dumps(e) for e in events)
    member = f"{PROJECT_ID}/{PROJECT_ID}_{start[0:4]}-{start[4:6]}-{start[6:8]}_{start[9:11]}#0.json.gz"
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(member, gzip.compress(lines.encode()))
    return Response(content=archive.getvalue(), media_type="application/zip")


@router.get("/api/3/cohorts")
async def list_cohorts(request: Request, includeSyncInfo: bool = Query(False)):
    require_basic_auth(request)
    return {
        "cohorts": [
            {
                "appId": 12345, "archived": False, "chart_id": "abc123",
                "createdAt": 1719835200000,
                "description": "Users who signed up in the last 30 days",
                "finished": True, "id": "cohort_001",
                "is_hidden": False, "is_official": False,
                "lastComputed": 1720454400000, "lastMod": 1720454400000,
                "name": "New Signups (30d)",
                "owners": [{"email": "admin@acme.io", "name": "Admin User"}],
                "published": True, "size": 342, "type": "dynamic", "view_count": 15,
            },
            {
                "appId": 12345, "archived": False, "chart_id": "def456",
                "createdAt": 1718625600000,
                "description": "Users at risk of churning based on declining engagement",
                "finished": True, "id": "cohort_002",
                "is_hidden": False, "is_official": False,
                "lastComputed": 1720454400000, "lastMod": 1720454400000,
                "name": "Churn Risk",
                "owners": [{"email": "admin@acme.io", "name": "Admin User"}],
                "published": True, "size": 58, "type": "dynamic", "view_count": 42,
            },
        ],
    }


@router.get("/api/2/usersearch")
async def user_search(request: Request, user: str = Query(...)):
    require_basic_auth(request)
    matches = []
    for p in PEOPLE:
        if user.lower() in p.email.lower() or user.lower() in f"{p.first_name} {p.last_name}".lower():
            co = COMPANIES_BY_ID.get(p.company_id)
            sub = SUBSCRIPTIONS_BY_COMPANY.get(co.id) if co else None
            matches.append({
                "amplitude_id": 9876543210 + int(p.id.replace("p", "")),
                "user_id": f"user_{p.first_name.lower()}_{co.domain.split('.')[0]}" if co else f"user_{p.id}",
                "last_seen": f"{p.last_seen}T00:00:00.000000" if p.last_seen else None,
                "platform": "Web", "os": "Mac OS X", "device": "Mac",
                "country": "United States", "region": co.state if co else "CA",
                "city": co.city if co else "San Francisco", "language": "en-US",
                "user_properties": {
                    "email": p.email,
                    "name": f"{p.first_name} {p.last_name}",
                    "company": co.name if co else "",
                    "plan": sub.plan if sub else "free",
                    "company_domain": co.domain if co else "",
                },
            })
    return {"matches": matches, "type": "match_user_or_device_id"}
