def with_name(
    payload: dict, first_field: str, last_field: str, source_record: dict | None = None
) -> dict:
    fields = source_record if source_record is not None else payload
    parts = [str(fields.get(key) or "").strip() for key in (first_field, last_field)]
    name = " ".join(part for part in parts if part)
    record = dict(payload)
    if name:
        record["_full_name"] = name
    return record
