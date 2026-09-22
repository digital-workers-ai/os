from urllib.parse import urlsplit

from app.engine import spy

PLATFORM = "linkedin"


def _segment(url) -> str | None:
    if not isinstance(url, str):
        return None
    return urlsplit(url).path.rstrip("/").rpartition("/")[2]


def _handles(payload: dict) -> list[str]:
    discovery = payload.get("discovery_input")
    discovered = discovery.get("url") if isinstance(discovery, dict) else None
    candidates = (
        payload.get("user_id"),
        _segment(payload.get("use_url")),
        _segment(discovered),
    )
    return [handle for handle in candidates if isinstance(handle, str)]


def company_name(payload: dict) -> str | None:
    definition = spy.definition()
    for handle in _handles(payload):
        company = definition.by_linkedin(handle)
        if company is not None:
            return company.name
    title = payload.get("title")
    return title if isinstance(title, str) and title.strip() else None


def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type != "posts":
        return [payload]
    record = {**payload, "_platform": PLATFORM}
    name = company_name(payload)
    if name is not None:
        record["_company"] = name
    return [record]
