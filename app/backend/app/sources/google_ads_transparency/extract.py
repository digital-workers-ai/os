from app.engine import spy

PLATFORM = "google"
NO_TEXT = "NONE"


def _dict(value):
    return value if isinstance(value, dict) else {}


def _company_name(payload):
    creative = _dict(payload.get("creative"))
    request = _dict(payload.get("request"))
    advertiser_id = creative.get("advertiser_id") or request.get("advertiser_id")
    company = spy.definition().by_advertiser(advertiser_id)
    return company.name if company else request.get("company")


def _text(payload):
    choices = _dict(payload.get("response")).get("choices")
    first = choices[0] if isinstance(choices, list) and choices else None
    content = _dict(_dict(first).get("message")).get("content")
    text = content.strip() if isinstance(content, str) else ""
    return text if text and text.upper() != NO_TEXT else None


def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type == "creatives":
        record = {**payload, "_platform": PLATFORM}
        name = _company_name(payload)
        if name:
            record["_company"] = name
        return [record]
    if object_type == "creative_texts":
        text = _text(payload)
        return [{**payload, "_text": text} if text else dict(payload)]
    return [payload]
