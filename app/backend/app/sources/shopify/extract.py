from app.sources.hooks import with_name


def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type != "customers":
        return [payload]
    return [with_name(payload, "first_name", "last_name")]
