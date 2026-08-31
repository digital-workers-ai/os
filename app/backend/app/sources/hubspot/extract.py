from app.sources.hooks import with_name


def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type != "contacts":
        return [payload]
    return [
        with_name(
            payload,
            "firstname",
            "lastname",
            source_record=payload.get("properties") or {},
        )
    ]
