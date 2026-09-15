from urllib.parse import urlsplit

SOURCE = "serp"


def domain_of(link) -> str | None:
    host = urlsplit(str(link or "")).hostname
    return host.removeprefix("www.") if host else None


def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type != "organic_results":
        return [payload]
    domain = domain_of(payload.get("link"))
    if domain is None:
        return [payload]
    return [{**payload, "_domain": domain}]
