SOURCE = "twitter"

PLATFORM = "x"

_LABELS = {
    "impression_count": "_impressions",
    "like_count": "_likes",
    "retweet_count": "_shares",
    "reply_count": "_comments",
}
_INTERACTION_KEYS = ("like_count", "retweet_count", "reply_count")


def _is_number(value):
    return isinstance(value, int | float) and not isinstance(value, bool)


def _sum_present(stats, keys):
    present = [stats[key] for key in keys if _is_number(stats.get(key))]
    return sum(present) if present else None


def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type != "tweets":
        return [payload]
    metrics = payload.get("public_metrics")
    metrics = metrics if isinstance(metrics, dict) else {}
    record = {**payload, "_platform": PLATFORM}
    record.update(
        {label: metrics[name] for name, label in _LABELS.items() if name in metrics}
    )
    total = _sum_present(metrics, _INTERACTION_KEYS)
    if total is not None:
        record["_interactions"] = total
    return [record]
