PLATFORM = "linkedin"
STAMPED = ("ads", "ad_details")


def _dict(value):
    return value if isinstance(value, dict) else {}


def _preview(content):
    image = content.get("image")
    if isinstance(image, str) and image:
        return image
    pages = content.get("pages")
    first = pages[0] if isinstance(pages, list) and pages else None
    return first if isinstance(first, str) and first else None


def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type not in STAMPED:
        return [payload]
    record = {
        **payload,
        "_platform": PLATFORM,
        "_company": _dict(payload.get("request")).get("company"),
    }
    if object_type == "ads":
        preview = _preview(_dict(_dict(payload.get("ad")).get("content")))
        if preview:
            record["_preview"] = preview
    return [record]
