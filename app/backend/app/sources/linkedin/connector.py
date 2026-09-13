from datetime import UTC, datetime, timedelta

from app.sources.paginators import Offset
from app.sources.util import client_for, pick_id, store_all, window

SOURCE = "linkedin"

OBSERVED_AT = {"ad_accounts": "lastModified"}

ORGANIZATION = "urn:li:organization:1"

_ELEMENTS = Offset("elements", count_param="count", offset_param="start")

_DAY_MS = int(timedelta(days=1).total_seconds() * 1000)


def _ms(day: str) -> int:
    return int(datetime.fromisoformat(day).replace(tzinfo=UTC).timestamp() * 1000)


def _intervals(since: str, until: str) -> str:
    return (
        f"(timeRange:(start:{_ms(since)},end:{_ms(until) + _DAY_MS}),"
        "timeGranularityType:DAY)"
    )


def _day_id(record):
    start = (record.get("timeRange") or {}).get("start")
    if isinstance(start, bool) or not isinstance(start, int | float):
        return None
    day = datetime.fromtimestamp(start / 1000, UTC).date().isoformat()
    return f"{ORGANIZATION}|{day}"


async def pull(session, store):
    api = client_for(SOURCE)
    notes: dict = {}
    since, until = window()
    accounts = await api.get(
        "/adAccounts",
        params={"q": "search", "pageSize": 1},
        paginate="token_linkedin",
    )
    await store_all(
        session, store, accounts, source=SOURCE, object_type="ad_accounts", notes=notes
    )
    posts = await api.get(
        "/posts",
        params={"author": ORGANIZATION, "q": "author", "start": 0, "count": 100},
        paginate=_ELEMENTS,
    )
    await store_all(
        session, store, posts, source=SOURCE, object_type="posts", notes=notes
    )
    urns = [urn for urn in (pick_id(post, "id") for post in posts) if urn]
    if urns:
        stats = await api.get(
            "/organizationalEntityShareStatistics",
            params={
                "q": "organizationalEntity",
                "organizationalEntity": ORGANIZATION,
                "shares": f"List({','.join(urns)})",
            },
            paginate=_ELEMENTS,
        )
        await store_all(
            session,
            store,
            stats,
            source=SOURCE,
            object_type="post_stats",
            id_fields=("share",),
            notes=notes,
        )
    intervals = _intervals(since, until)
    followers = await api.get(
        "/organizationalEntityFollowerStatistics",
        params={
            "q": "organizationalEntity",
            "organizationalEntity": ORGANIZATION,
            "timeIntervals": intervals,
        },
        paginate=_ELEMENTS,
    )
    await store_all(
        session,
        store,
        followers,
        source=SOURCE,
        object_type="follower_stats",
        id_of=_day_id,
        notes=notes,
    )
    pages = await api.get(
        "/organizationPageStatistics",
        params={
            "q": "organization",
            "organization": ORGANIZATION,
            "timeIntervals": intervals,
        },
        paginate=_ELEMENTS,
    )
    await store_all(
        session,
        store,
        pages,
        source=SOURCE,
        object_type="page_stats",
        id_of=_day_id,
        notes=notes,
    )
    return notes or None
