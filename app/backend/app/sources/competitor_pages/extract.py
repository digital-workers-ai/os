from urllib.parse import urlsplit

SOURCE = "competitor_pages"


def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type != "pages":
        return [payload]
    record = {**payload}
    host = urlsplit(str(payload.get("url") or "")).hostname
    if host:
        record["_competitor_ref"] = host.removeprefix("www.")
    text = payload.get("text")
    if isinstance(text, str):
        record["_word_count"] = len(text.split())
    return [record]
