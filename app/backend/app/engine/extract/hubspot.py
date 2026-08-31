from app.engine.extract._compose import with_name

SOURCE = "hubspot"


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
