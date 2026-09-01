from urllib.parse import quote

from app.sources.util import client_for

SOURCE = "zoom"

OBSERVED_AT = {"meetings": "start_time"}

_MAX_PAGES = 100


def participants_path(uuid: str) -> str:
    text = str(uuid)
    once = quote(text, safe="")
    escaped = quote(once, safe="") if text.startswith("/") or "//" in text else once
    return f"/v2/past_meetings/{escaped}/participants"


def _count(notes: dict, key: str) -> None:
    notes[key] = notes.get(key, 0) + 1


async def pull(session, store):
    api = client_for(SOURCE)
    notes: dict = {}
    token, pages = None, 0

    while pages < _MAX_PAGES:
        pages += 1
        params = {"page_size": 30}
        if token:
            params["next_page_token"] = token
        page = await api.get("/v2/users/me/recordings", params=params)

        for meeting in page.get("meetings", []):
            uuid = meeting.get("uuid")
            if not uuid:
                _count(notes, "missing_uuid")
                continue

            record = dict(meeting)
            transcript_url = next(
                (
                    f.get("download_url")
                    for f in meeting.get("recording_files") or []
                    if f.get("file_type") == "TRANSCRIPT"
                ),
                None,
            )
            if transcript_url:
                path = transcript_url.split("/v2/", 1)[-1]
                try:
                    record["_transcript_vtt"] = await api.get_text(f"/v2/{path}")
                except Exception as e:
                    _count(notes, "transcript_fetch_failed")
                    record["_transcript_error"] = f"{type(e).__name__}: {e}"[:200]
            else:
                _count(notes, "no_transcript")

            try:
                people = await api.get(
                    participants_path(uuid), params={"page_size": 300}
                )
                record["_participants"] = people.get("participants", [])
            except Exception:
                _count(notes, "participants_fetch_failed")

            await store(
                session,
                source=SOURCE,
                object_type="meetings",
                source_id=str(uuid),
                raw_payload=record,
            )

        token = page.get("next_page_token")
        if not token:
            break
    else:
        notes["page_guard"] = _MAX_PAGES
        api.truncate(f"zoom page guard {_MAX_PAGES} reached")

    return notes or None
