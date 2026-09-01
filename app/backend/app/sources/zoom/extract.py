import re
from datetime import UTC, datetime, timedelta

from app.engine.resolver import FREE_MAIL_DOMAINS
from app.engine.transforms import MAX_TRANSCRIPT_CHARS

SOURCE = "zoom"

_CUE_TIME = re.compile(r"^[\d:.]+\s*-->\s*[\d:.]+")
_SPEAKER = re.compile(r"^(?P<speaker>[^:]{1,80}):\s*(?P<text>.+)$")


def parse_vtt(text: str) -> tuple[list, int]:
    utterances, unattributed = [], 0
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip()):
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines or lines[0].upper().startswith("WEBVTT"):
            continue
        body = [
            line for line in lines if not line.isdigit() and not _CUE_TIME.match(line)
        ]
        if not body:
            continue
        match = _SPEAKER.match(" ".join(body))
        if match:
            utterances.append(
                (match.group("speaker").strip(), match.group("text").strip())
            )
        else:
            unattributed += 1
    return utterances, unattributed


def dialogue(utterances: list) -> str:
    return "\n".join(f"{speaker}: {text}" for speaker, text in utterances)


def _transcript(payload: dict, record: dict, skips: list) -> None:
    vtt = payload.get("_transcript_vtt")
    if isinstance(vtt, str) and vtt.strip():
        utterances, unattributed = parse_vtt(vtt)
        if utterances:
            text = dialogue(utterances)
            if len(text) > MAX_TRANSCRIPT_CHARS:
                text = text[:MAX_TRANSCRIPT_CHARS]
                skips.append(["_transcript_text", "truncated_at_cap"])
            record["_transcript_text"] = text
        else:
            skips.append(["_transcript_text", "vtt_had_no_speech"])
        if unattributed:
            skips.append(["_transcript_text", "cues_without_a_speaker"])
    elif payload.get("_transcript_error"):
        skips.append(["_transcript_text", "download_failed"])


def _external_email(payload: dict, record: dict, skips: list) -> None:
    host = str(payload.get("host_email") or "").strip().lower()
    host_domain = host.rsplit("@", 1)[-1] if "@" in host else ""
    if not host_domain:
        skips.append(["_external_email", "no_host_email"])
        return
    for person in payload.get("_participants") or []:
        if not isinstance(person, dict):
            continue
        email = str(person.get("user_email") or "").strip().lower()
        if "@" not in email:
            continue
        domain = email.rsplit("@", 1)[-1]
        if domain == host_domain:
            continue
        record["_external_email"] = email
        if domain in FREE_MAIL_DOMAINS:
            skips.append(["_external_domain", "free_mail_domain"])
        else:
            record["_external_domain"] = domain
        return
    skips.append(["_external_email", "no_external_attendee"])


def _ended_at(payload: dict, record: dict, skips: list) -> None:
    start, minutes = payload.get("start_time"), payload.get("duration")
    if isinstance(start, str) and isinstance(minutes, int | float):
        try:
            begin = datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        except ValueError:
            skips.append(["_ended_at", "unparseable_start_time"])
            return
        record["_ended_at"] = (begin + timedelta(minutes=float(minutes))).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )


def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type != "meetings":
        return [payload]
    record = dict(payload)
    skips: list = []
    _transcript(payload, record, skips)
    _external_email(payload, record, skips)
    _ended_at(payload, record, skips)
    if skips:
        record["_hook_skips"] = skips
    return [record]
