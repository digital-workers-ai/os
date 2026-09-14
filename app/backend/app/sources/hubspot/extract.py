from app.sources.hooks import with_name

CLOSED_FLAGS = ("hs_is_closed_won", "hs_is_closed")


def _deal_status(properties: dict) -> str | None:
    if not any(flag in properties for flag in CLOSED_FLAGS):
        return None
    if properties.get("hs_is_closed_won") == "true":
        return "closed_won"
    if properties.get("hs_is_closed") == "true":
        return "closed_lost"
    return "open"


def reshape(object_type: str, payload: dict) -> list[dict]:
    properties = payload.get("properties") or {}
    if object_type == "contacts":
        return [with_name(payload, "firstname", "lastname", source_record=properties)]
    if object_type == "deals":
        status = _deal_status(properties)
        return [payload if status is None else {**payload, "_status": status}]
    return [payload]
