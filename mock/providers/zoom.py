"""
Zoom Meeting API v2 mock provider.
Contract: seeds/docs/29-zoom.md

Cloud recordings with audio transcripts. Three things make Zoom awkward and all
three are reproduced here rather than smoothed over:

  - the recording list is paginated by `next_page_token`, not a cursor or offset
  - the transcript is not in the payload. The recording entry carries a
    `download_url` and the file has to be fetched separately.
  - that file is WEBVTT — subtitles, not JSON. Speaker attribution lives in the
    cue text as `Name: utterance`, which is a convention, not a format.

Participants come from a different endpoint again, keyed by meeting UUID.
"""

import base64

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from seeds.helpers import require_bearer
from seeds.world import COMPANIES_BY_ID, PEOPLE_BY_ID, SALES_CALLS, SALES_CALLS_BY_ID

router = APIRouter()

_HOST = "https://api.zoom.us"


def _meeting_id(call) -> int:
    """Zoom meeting ids are 11-digit numbers, not the string ids the rest of
    the estate uses."""
    return 81000000000 + int(call.id[2:])


def _uuid(call) -> str:
    """A base64 UUID, which Zoom double-encodes in URLs when it contains `/`."""
    return base64.b64encode(f"os-zoom-{call.id}".encode()).decode()


def _end_time(started_at: str, duration_min: int) -> str:
    from datetime import datetime, timedelta
    start = datetime.strptime(started_at, "%Y-%m-%dT%H:%M:%SZ")
    return (start + timedelta(minutes=duration_min)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _recording(call) -> dict:
    mid = _meeting_id(call)
    company = COMPANIES_BY_ID.get(call.company_id)
    return {
        "uuid": _uuid(call),
        "id": mid,
        "account_id": "acct_os_mock",
        "host_id": "usr_" + call.host_email.split("@")[0],
        "host_email": call.host_email,
        "topic": call.topic,
        "type": 2,
        "start_time": call.started_at,
        "timezone": "UTC",
        "duration": call.duration_min,
        "total_size": 18_400_000 + call.duration_min * 1000,
        "recording_count": 2,
        "share_url": f"{_HOST}/rec/share/{_uuid(call)}",
        "recording_files": [
            {
                "id": f"rf_{call.id}_audio",
                "meeting_id": _uuid(call),
                "recording_start": call.started_at,
                "recording_end": _end_time(call.started_at, call.duration_min),
                "file_type": "M4A",
                "file_extension": "M4A",
                "file_size": 18_000_000,
                "recording_type": "audio_only",
                "status": "completed",
                "download_url": f"{_HOST}/rec/download/{call.id}.m4a",
            },
            {
                "id": f"rf_{call.id}_transcript",
                "meeting_id": _uuid(call),
                "recording_start": call.started_at,
                "recording_end": _end_time(call.started_at, call.duration_min),
                # The connector must select on file_type — there is no other
                # marker, and the audio file sits in the same list.
                "file_type": "TRANSCRIPT",
                "file_extension": "VTT",
                "file_size": 4200,
                "recording_type": "audio_transcript",
                "status": "completed",
                "download_url": f"{_HOST}/v2/meetings/{mid}/transcript.vtt",
            },
        ],
        # Not part of Zoom's schema; the mock carries it so a reader can tell
        # which account a call belongs to without resolving participants.
        "_company_domain": company.domain if company else None,
    }


def _vtt(call) -> str:
    """WEBVTT with `Name: utterance` cue text — Zoom's own convention."""
    from datetime import datetime, timedelta

    start = datetime.strptime(call.started_at, "%Y-%m-%dT%H:%M:%SZ")
    lines = ["WEBVTT", ""]
    # Spread the utterances evenly across the call's duration; a real file has
    # true timings, but even spacing keeps the fixture deterministic.
    step = max(1, (call.duration_min * 60) // max(1, len(call.transcript)))
    for i, (speaker, text) in enumerate(call.transcript, start=1):
        cue_start = start + timedelta(seconds=(i - 1) * step)
        cue_end = start + timedelta(seconds=i * step - 1)
        fmt = "%H:%M:%S.000"
        lines += [str(i),
                  f"{cue_start.strftime(fmt)} --> {cue_end.strftime(fmt)}",
                  f"{speaker}: {text}",
                  ""]
    return "\n".join(lines)


@router.get("/v2/users/me/recordings")
async def list_recordings(
    request: Request,
    page_size: int = Query(30, ge=1, le=300),
    next_page_token: str = Query(None),
):
    require_bearer(request)
    calls = list(SALES_CALLS)

    start = 0
    if next_page_token:
        try:
            start = int(base64.b64decode(next_page_token).decode())
        except Exception:
            raise HTTPException(status_code=400, detail={
                "code": 300, "message": "Invalid next page token."})

    page = calls[start:start + page_size]
    nxt = ""
    if start + page_size < len(calls):
        nxt = base64.b64encode(str(start + page_size).encode()).decode()

    return {
        "from": "2026-07-01",
        "to": "2026-07-31",
        "page_count": 1 + (len(calls) - 1) // page_size,
        "page_size": page_size,
        "total_records": len(calls),
        # Zoom sends an EMPTY STRING, not null, when there are no more pages.
        "next_page_token": nxt,
        "meetings": [_recording(c) for c in page],
    }


@router.get("/v2/meetings/{meeting_id}/transcript.vtt",
            response_class=PlainTextResponse)
async def download_transcript(request: Request, meeting_id: int):
    require_bearer(request)
    for call in SALES_CALLS:
        if _meeting_id(call) == meeting_id:
            return PlainTextResponse(_vtt(call), media_type="text/vtt")
    raise HTTPException(status_code=404, detail={
        "code": 3301, "message": "There is no recording for this meeting."})


@router.get("/v2/past_meetings/{meeting_uuid}/participants")
async def list_participants(
    request: Request,
    meeting_uuid: str,
    page_size: int = Query(30, ge=1, le=300),
    next_page_token: str = Query(None),
):
    require_bearer(request)
    call = next((c for c in SALES_CALLS if _uuid(c) == meeting_uuid), None)
    if call is None:
        raise HTTPException(status_code=404, detail={
            "code": 3001, "message": "Meeting does not exist."})
    prospect = PEOPLE_BY_ID[call.prospect_id]
    return {
        "page_count": 1,
        "page_size": page_size,
        "total_records": 2,
        "next_page_token": "",
        "participants": [
            {"id": f"usr_{call.host_email.split('@')[0]}",
             "name": call.host_email.split("@")[0].title(),
             "user_email": call.host_email,
             "join_time": call.started_at,
             "leave_time": _end_time(call.started_at, call.duration_min)},
            {"id": f"ext_{prospect.id}",
             "name": f"{prospect.first_name} {prospect.last_name}",
             "user_email": prospect.email,
             "join_time": call.started_at,
             "leave_time": _end_time(call.started_at, call.duration_min)},
        ],
    }


@router.get("/v2/meetings/{meeting_id}")
async def get_meeting(request: Request, meeting_id: int):
    require_bearer(request)
    for call in SALES_CALLS:
        if _meeting_id(call) == meeting_id:
            return _recording(call)
    raise HTTPException(status_code=404, detail={
        "code": 3001, "message": "Meeting does not exist."})
