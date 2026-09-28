from urllib.parse import urlsplit

from app.engine import spy

PLATFORM = "instagram"


def _handle(url) -> str | None:
    if not isinstance(url, str):
        return None
    return urlsplit(url).path.rstrip("/").rpartition("/")[2]


def company_name(payload: dict) -> str | None:
    definition = spy.definition()
    discovery = payload.get("discovery_input")
    discovered = discovery.get("url") if isinstance(discovery, dict) else None
    for handle in (_handle(discovered), payload.get("user_posted")):
        company = definition.by_instagram(handle)
        if company is not None:
            return company.name
    return None


def _preview(payload: dict) -> str | None:
    thumbnail = payload.get("thumbnail")
    return thumbnail if isinstance(thumbnail, str) and thumbnail else None


def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type != "posts":
        return [payload]
    record = {**payload, "_platform": PLATFORM}
    name = company_name(payload)
    if name is not None:
        record["_company"] = name
    preview = _preview(payload)
    if preview is not None:
        record["_preview"] = preview
    return [record]
