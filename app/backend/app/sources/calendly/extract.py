def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type != "scheduled_events":
        return [payload]
    record = dict(payload)
    invitees = payload.get("_invitees") or []
    if not isinstance(invitees, list) or not invitees:
        record["_hook_skips"] = [["_invitee_email", "no_invitees"]]
        return [record]
    first = invitees[0] if isinstance(invitees[0], dict) else {}
    record["_invitee_email"] = str(first.get("email") or "").strip()
    if len(invitees) > 1:
        record["_hook_skips"] = [["_invitee_email", "multi_invitee_meeting"]]
    return [record]
