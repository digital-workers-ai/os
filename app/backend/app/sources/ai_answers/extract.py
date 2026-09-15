SOURCE = "ai_answers"


def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type != "mentions":
        return [payload]
    engine = payload.get("_engine")
    if not engine:
        return [payload]
    return [{**payload, "engine": engine}]
