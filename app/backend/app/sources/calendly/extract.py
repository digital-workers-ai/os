def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type != "scheduled_events":
        return [payload]
    record = dict(payload)
    memberships = payload.get("event_memberships") or []
    if not isinstance(memberships, list) or not memberships:
        record["_hook_skips"] = [["_host_email", "no_event_memberships"]]
        return [record]
    first = memberships[0] if isinstance(memberships[0], dict) else {}
    record["_host_email"] = str(first.get("user_email") or "").strip()
    if len(memberships) > 1:
        record["_hook_skips"] = [["_host_email", "multi_host_meeting"]]
    return [record]
