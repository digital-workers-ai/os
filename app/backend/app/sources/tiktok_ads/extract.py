from app.engine import spy

PLATFORM = "tiktok"
LIBRARY = "https://library.tiktok.com/ads/detail/?ad_id="


def _dict(value):
    return value if isinstance(value, dict) else {}


def _company_name(request, item):
    advertiser_id = item.get("advertiser_id") or request.get("advertiser_id")
    company = spy.definition().by_tiktok_advertiser(advertiser_id)
    return company.name if company else request.get("company")


def _preview(item):
    cover = item.get("cover_image")
    if isinstance(cover, str) and cover:
        return cover
    images = item.get("image_urls")
    first = images[0] if isinstance(images, list) and images else None
    return first if isinstance(first, str) and first else None


def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type != "ads":
        return [payload]
    request = _dict(payload.get("request"))
    item = _dict(payload.get("ad"))
    record = {
        **payload,
        "_platform": PLATFORM,
        "_company": _company_name(request, item),
    }
    preview = _preview(item)
    if preview:
        record["_preview"] = preview
    ad_id = item.get("id")
    if isinstance(ad_id, str) and ad_id:
        record["_url"] = f"{LIBRARY}{ad_id}"
    return [record]
