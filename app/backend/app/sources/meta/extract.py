SOURCE = "meta"

_PLATFORMS = {
    "page_posts": "facebook",
    "page_insights": "facebook",
    "post_insights": "facebook",
    "ig_media": "instagram",
    "ig_insights": "instagram",
    "media_insights": "instagram",
}

_METRICS = {
    "page_insights": {
        "page_impressions_unique": "_reach",
        "page_impressions": "_impressions",
        "page_post_engagements": "_engaged",
        "page_fan_adds": "_follows",
        "page_fan_removes": "_unfollows",
        "page_views_total": "_profile_views",
    },
    "ig_insights": {
        "reach": "_reach",
        "impressions": "_impressions",
        "accounts_engaged": "_engaged",
        "follower_count": "_follows",
        "profile_views": "_profile_views",
    },
    "post_insights": {
        "post_impressions_unique": "_reach",
        "post_impressions": "_impressions",
        "post_clicks": "_clicks",
    },
    "media_insights": {
        "reach": "_reach",
        "impressions": "_impressions",
        "views": "_views",
        "saved": "_saves",
    },
}

_DAILY = {"page_insights", "ig_insights"}

_INTERACTION_PARTS = {
    "page_posts": (
        ("likes", "summary", "total_count"),
        ("comments", "summary", "total_count"),
        ("shares", "count"),
    ),
    "ig_media": (("like_count",), ("comments_count",)),
}


def _dict(value):
    return value if isinstance(value, dict) else {}


def _dig(payload, path):
    node = payload
    for key in path:
        node = _dict(node).get(key)
    return node


def _is_number(value):
    return isinstance(value, int | float) and not isinstance(value, bool)


def _sum_present(payload, parts):
    present = [n for n in (_dig(payload, part) for part in parts) if _is_number(n)]
    return sum(present) if present else None


def _stamp(record, label, value):
    if value is not None:
        record[label] = value


def reshape(object_type: str, payload: dict) -> list[dict]:
    platform = _PLATFORMS.get(object_type)
    if platform is None:
        return [payload]
    record = {**payload, "_platform": platform}
    values = _dict(payload.get("values"))
    labels = _METRICS.get(object_type, {})
    record.update(
        {label: values[name] for name, label in labels.items() if name in values}
    )
    if object_type in _DAILY:
        _stamp(record, "_report_date", payload.get("date"))
    _stamp(
        record,
        "_interactions",
        _sum_present(payload, _INTERACTION_PARTS.get(object_type, ())),
    )
    return [record]
