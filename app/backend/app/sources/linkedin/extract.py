from datetime import UTC, datetime

SOURCE = "linkedin"

PLATFORM = "linkedin"

_SHARE_LABELS = {
    "impressionCount": "_impressions",
    "likeCount": "_likes",
    "commentCount": "_comments",
    "shareCount": "_shares",
    "clickCount": "_clicks",
}
_INTERACTION_KEYS = ("likeCount", "commentCount", "shareCount")
_GAIN_KEYS = ("organicFollowerGain", "paidFollowerGain")
_HANDLED = {"posts", "post_stats", "follower_stats", "page_stats"}


def _dict(value):
    return value if isinstance(value, dict) else {}


def _dig(payload, *keys):
    node = payload
    for key in keys:
        node = _dict(node).get(key)
    return node


def _is_number(value):
    return isinstance(value, int | float) and not isinstance(value, bool)


def _moment(millis):
    if not _is_number(millis):
        return None
    return datetime.fromtimestamp(millis / 1000, UTC)


def _iso(millis):
    moment = _moment(millis)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ") if moment else None


def _day(millis):
    moment = _moment(millis)
    return moment.date().isoformat() if moment else None


def _sum_present(stats, keys):
    present = [stats[key] for key in keys if _is_number(stats.get(key))]
    return sum(present) if present else None


def _stamp(record, label, value):
    if value is not None:
        record[label] = value


def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type not in _HANDLED:
        return [payload]
    record = {**payload, "_platform": PLATFORM}
    if object_type == "posts":
        _stamp(record, "_posted_at", _iso(payload.get("publishedAt")))
    elif object_type == "post_stats":
        stats = _dict(payload.get("totalShareStatistics"))
        record.update(
            {
                label: stats[name]
                for name, label in _SHARE_LABELS.items()
                if name in stats
            }
        )
        _stamp(record, "_interactions", _sum_present(stats, _INTERACTION_KEYS))
    else:
        _stamp(record, "_report_date", _day(_dig(payload, "timeRange", "start")))
        _stamp(
            record,
            "_follows",
            _sum_present(_dict(payload.get("followerGains")), _GAIN_KEYS),
        )
        _stamp(
            record,
            "_profile_views",
            _dig(payload, "totalPageStatistics", "views", "allPageViews", "pageViews"),
        )
    return [record]
