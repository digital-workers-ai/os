from app.sources.google_analytics.connector import REPORT_SCHEMA
from app.sources.hooks import ExtractError

SOURCE = "google_analytics"


def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type != "report_rows":
        return [payload]
    dimensions = [d.get("value") for d in payload.get("dimensionValues") or []]
    metrics = [m.get("value") for m in payload.get("metricValues") or []]
    if len(dimensions) != len(REPORT_SCHEMA["dimensions"]) or len(metrics) != len(
        REPORT_SCHEMA["metrics"]
    ):
        raise ExtractError(
            f"report row has {len(dimensions)}/{len(metrics)} dimension/metric "
            f"values but the connector's query declares "
            f"{len(REPORT_SCHEMA['dimensions'])}/{len(REPORT_SCHEMA['metrics'])}"
        )
    record = dict(payload)
    for label, value in zip(REPORT_SCHEMA["dimensions"], dimensions, strict=True):
        record[f"_{label}"] = value
    for label, value in zip(REPORT_SCHEMA["metrics"], metrics, strict=True):
        record[f"_{label}"] = value
    return [record]
