from app.sources.hooks import with_name

SOURCE = "activecampaign"


def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type != "contacts":
        return [payload]
    return [with_name(payload, "firstName", "lastName")]
