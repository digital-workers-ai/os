from app.sources.hooks import with_name


def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type != "contacts":
        return [payload]
    record = with_name(payload, "firstName", "lastName")
    record.setdefault("_full_name", None)
    return [record]
