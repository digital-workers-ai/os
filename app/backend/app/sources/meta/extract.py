SOURCE = "meta"

_PLATFORMS = {"page_posts": "facebook", "ig_media": "instagram"}


def reshape(object_type: str, payload: dict) -> list[dict]:
    platform = _PLATFORMS.get(object_type)
    if platform is None:
        return [payload]
    return [{**payload, "_platform": platform}]
