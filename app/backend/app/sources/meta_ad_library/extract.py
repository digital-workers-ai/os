SOURCE = "meta_ad_library"

PLATFORM = "meta"


def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type != "ads":
        return [payload]
    record = {**payload, "_platform": PLATFORM}
    bodies = payload.get("ad_creative_bodies")
    if isinstance(bodies, list) and bodies:
        record["_name"] = bodies[0]
    return [record]
