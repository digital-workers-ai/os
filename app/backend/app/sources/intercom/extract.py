def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type != "conversations":
        return [payload]
    source = payload.get("source")
    author = source.get("author") if isinstance(source, dict) else None
    record = dict(payload)
    record["_author_email"] = author.get("email") if isinstance(author, dict) else None
    return [record]
