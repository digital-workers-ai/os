from app.engine import spy
from app.sources import brightdata
from app.sources.util import client_for, store_all

SOURCE = "instagram_posts"

OBSERVED_AT = {"posts": "date_posted"}

DATASET_ID = "gd_lk5ns7kz21pck8jpis"
DISCOVER_BY = "url"
POLL_LIMIT = 60


def profile_urls() -> list[str]:
    return [
        f"https://www.instagram.com/{company.instagram}/"
        for company in spy.definition().competitors
        if company.instagram
    ]


async def pull(session, store):
    api = client_for(SOURCE)
    urls = profile_urls()
    if not urls:
        return {"no_instagram_handles": 1}
    notes: dict = {}
    posts = []
    for record in await brightdata.discover(
        api,
        SOURCE,
        dataset_id=DATASET_ID,
        discover_by=DISCOVER_BY,
        urls=urls,
        poll_limit=POLL_LIMIT,
    ):
        if brightdata.failed(record):
            notes["dead_pages"] = notes.get("dead_pages", 0) + 1
            continue
        posts.append(record)
    await store_all(
        session,
        store,
        posts,
        source=SOURCE,
        object_type="posts",
        id_fields=("post_id",),
        notes=notes,
    )
    return notes or None
