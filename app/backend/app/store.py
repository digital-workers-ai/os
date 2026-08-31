import hashlib
import json

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RawEvent

_MAX_SOURCE_ID = 256


def payload_sha(raw_payload: dict) -> str:
    canonical = json.dumps(raw_payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _has_nul(value) -> bool:
    if isinstance(value, str):
        return "\x00" in value
    if isinstance(value, dict):
        return any(_has_nul(k) or _has_nul(v) for k, v in value.items())
    if isinstance(value, list | tuple):
        return any(_has_nul(item) for item in value)
    return False


def _validate(source: str, object_type: str, source_id: str, raw_payload) -> None:
    if not source or not isinstance(source, str):
        raise ValueError("source must be a non-empty string")
    if not object_type or not isinstance(object_type, str):
        raise ValueError("object_type is required and must be a non-empty string")
    if not isinstance(source_id, str) or not source_id.strip():
        raise ValueError("source_id must be a non-empty string")
    if len(source_id) > _MAX_SOURCE_ID:
        raise ValueError(f"source_id exceeds {_MAX_SOURCE_ID} chars: {source_id[:64]}…")
    if not isinstance(raw_payload, dict):
        raise ValueError(
            f"raw_payload must be a dict, got {type(raw_payload).__name__}"
        )
    if _has_nul(raw_payload):
        raise ValueError("raw_payload contains a null byte — refusing to store")


async def save_raw(
    session: AsyncSession,
    *,
    source: str,
    object_type: str,
    source_id: str,
    raw_payload: dict,
) -> bool:
    _validate(source, object_type, source_id, raw_payload)
    sha = payload_sha(raw_payload)

    newest = (
        await session.execute(
            select(RawEvent.payload_sha)
            .where(
                RawEvent.source == source,
                RawEvent.object_type == object_type,
                RawEvent.source_id == source_id,
            )
            .order_by(RawEvent.seq.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if newest == sha:
        return False

    session.add(
        RawEvent(
            source=source,
            object_type=object_type,
            source_id=source_id,
            raw_payload=raw_payload,
            payload_sha=sha,
        )
    )
    await session.flush()
    return True


def first_seen_query():
    return select(
        RawEvent.source,
        RawEvent.object_type,
        RawEvent.source_id,
        func.min(RawEvent.seq),
        func.min(RawEvent.ingested_at),
    ).group_by(RawEvent.source, RawEvent.object_type, RawEvent.source_id)


def latest_rows_query():
    return (
        select(RawEvent)
        .distinct(RawEvent.source, RawEvent.object_type, RawEvent.source_id)
        .order_by(
            RawEvent.source,
            RawEvent.object_type,
            RawEvent.source_id,
            RawEvent.seq.desc(),
        )
    )
