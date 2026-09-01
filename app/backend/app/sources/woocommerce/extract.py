from app.sources.hooks import with_name


def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type == "customers":
        return [with_name(payload, "first_name", "last_name")]
    if object_type == "orders":
        record = with_name(
            payload,
            "first_name",
            "last_name",
            source_record=payload.get("billing") or {},
        )
        placed_at = payload.get("date_created_gmt") or payload.get("date_created")
        if placed_at:
            record["_placed_at"] = placed_at
        return [record]
    return [payload]
