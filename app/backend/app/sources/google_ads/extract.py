SOURCE = "google_ads"


def reshape(object_type: str, payload: dict) -> list[dict]:
    campaign_id = (payload.get("campaign") or {}).get("id")
    if object_type != "daily_campaigns" or campaign_id is None:
        return [payload]
    return [{**payload, "_campaign_ref": campaign_id}]
