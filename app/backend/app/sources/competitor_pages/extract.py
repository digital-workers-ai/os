import hashlib

SOURCE = "competitor_pages"


def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type != "pages":
        return [payload]
    markdown = payload.get("markdown")
    if not isinstance(markdown, str):
        return [payload]
    return [
        {
            **payload,
            "_word_count": len(markdown.split()),
            "_body_sha": hashlib.sha256(markdown.encode()).hexdigest(),
        }
    ]
