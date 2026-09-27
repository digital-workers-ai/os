from app.engine import spy

PLATFORM = "meta"
LIBRARY = "https://www.facebook.com/ads/library/?id="


def _dict(value):
    return value if isinstance(value, dict) else {}


def _text(value):
    return value if isinstance(value, str) and value else None


def _first(snapshot, key, field):
    items = snapshot.get(key)
    first = items[0] if isinstance(items, list) and items else None
    return _text(_dict(first).get(field))


def _company_name(request, item):
    page_id = item.get("page_id") or request.get("page_id")
    company = spy.definition().by_meta_page(page_id)
    return company.name if company else request.get("company")


def _category(snapshot):
    display_format = _text(snapshot.get("display_format"))
    return display_format.lower() if display_format else None


def _url(item):
    ad_id = _text(item.get("ad_archive_id"))
    return f"{LIBRARY}{ad_id}" if ad_id else None


def _stamps(item):
    snapshot = _dict(item.get("snapshot"))
    return {
        "_name": _text(_dict(snapshot.get("body")).get("text"))
        or _text(snapshot.get("title")),
        "_category": _category(snapshot),
        "_preview": _first(snapshot, "videos", "video_preview_image_url")
        or _first(snapshot, "images", "original_image_url")
        or _first(snapshot, "cards", "original_image_url"),
        "_media": _first(snapshot, "videos", "video_hd_url")
        or _first(snapshot, "videos", "video_sd_url"),
        "_url": _url(item),
    }


def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type != "ads":
        return [payload]
    request = _dict(payload.get("request"))
    item = _dict(payload.get("ad"))
    record = {
        **payload,
        "_platform": PLATFORM,
        "_company": _company_name(request, item),
        **{key: value for key, value in _stamps(item).items() if value},
    }
    return [record]
