SOURCE = "pinterest"

PLATFORM = "pinterest"

_PIN_LABELS = {"IMPRESSION": "_impressions", "SAVE": "_saves"}
_CLICK_KEYS = ("PIN_CLICK", "OUTBOUND_CLICK")
_DAY_LABELS = {
    "IMPRESSION": "_impressions",
    "ENGAGEMENT": "_engaged",
    "TOTAL_AUDIENCE": "_reach",
}


def _dict(value):
    return value if isinstance(value, dict) else {}


def _is_number(value):
    return isinstance(value, int | float) and not isinstance(value, bool)


def _sum_present(stats, keys):
    present = [stats[key] for key in keys if _is_number(stats.get(key))]
    return sum(present) if present else None


def _copy(metrics, labels):
    return {label: metrics[name] for name, label in labels.items() if name in metrics}


def _stamp(record, label, value):
    if value is not None:
        record[label] = value


def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type == "pins":
        metrics = _dict(_dict(payload.get("pin_metrics")).get("all_time"))
        record = {**payload, "_platform": PLATFORM, **_copy(metrics, _PIN_LABELS)}
        _stamp(record, "_clicks", _sum_present(metrics, _CLICK_KEYS))
        return [record]
    if object_type == "account_analytics":
        metrics = _dict(payload.get("metrics"))
        record = {**payload, "_platform": PLATFORM, **_copy(metrics, _DAY_LABELS)}
        _stamp(record, "_report_date", payload.get("date"))
        return [record]
    return [payload]
