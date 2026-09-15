from datetime import UTC, datetime

SOURCE = "google_ads_transparency"

PLATFORM = "google"

_SEEN_LABELS = {"first_shown": "_first_seen", "last_shown": "_last_seen"}


def _is_number(value):
    return isinstance(value, int | float) and not isinstance(value, bool)


def _iso(seconds):
    if not _is_number(seconds):
        return None
    return datetime.fromtimestamp(seconds, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _stamp(record, label, value):
    if value is not None:
        record[label] = value


def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type != "creatives":
        return [payload]
    record = {**payload, "_platform": PLATFORM}
    for field, label in _SEEN_LABELS.items():
        _stamp(record, label, _iso(payload.get(field)))
    if payload.get("text"):
        record["_name"] = payload["text"]
    return [record]
