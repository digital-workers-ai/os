SOURCE = "linkedin_posts"

PLATFORM = "linkedin"


def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type != "posts":
        return [payload]
    return [{**payload, "_platform": PLATFORM}]
