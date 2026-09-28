from urllib.parse import urlsplit

from app.engine import spy

PLATFORM = "x"


def _handle(url) -> str | None:
    if not isinstance(url, str):
        return None
    return urlsplit(url).path.rstrip("/").rpartition("/")[2]


def company_name(payload: dict) -> str | None:
    definition = spy.definition()
    discovery = payload.get("discovery_input")
    discovered = discovery.get("url") if isinstance(discovery, dict) else None
    for handle in (_handle(discovered), payload.get("user_posted")):
        company = definition.by_x(handle)
        if company is not None:
            return company.name
    name = payload.get("name")
    return name if isinstance(name, str) and name.strip() else None


def _category(payload: dict) -> str:
    if payload.get("is_repost") is True:
        return "repost"
    if isinstance(payload.get("videos"), list) and payload["videos"]:
        return "video"
    if isinstance(payload.get("photos"), list) and payload["photos"]:
        return "image"
    return "text"


def _preview(payload: dict) -> str | None:
    photos = payload.get("photos")
    if not isinstance(photos, list):
        return None
    return next((photo for photo in photos if isinstance(photo, str) and photo), None)


def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type != "posts":
        return [payload]
    record = {**payload, "_platform": PLATFORM, "_category": _category(payload)}
    name = company_name(payload)
    if name is not None:
        record["_company"] = name
    preview = _preview(payload)
    if preview is not None:
        record["_preview"] = preview
    return [record]
