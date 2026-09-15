SOURCE = "linkedin_posts"

PLATFORM = "linkedin"


def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type != "posts":
        return [payload]
    record = {**payload, "_platform": PLATFORM}
    domain = payload.get("_domain")
    if domain:
        record["_competitor_ref"] = domain
    return [record]
