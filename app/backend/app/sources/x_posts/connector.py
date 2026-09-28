from app.engine import spy
from app.sources import brightdata
from app.sources.util import client_for, store_all

SOURCE = "x_posts"

OBSERVED_AT = {"posts": "date_posted"}

DATASET_ID = "gd_lwxkxvnf1cynvib9co"
DISCOVER_BY = "profile_url"
POLL_LIMIT = 30


def profile_urls() -> list[str]:
    return [
        f"https://x.com/{company.x}"
        for company in spy.definition().competitors
        if company.x
    ]


async def pull(session, store):
    api = client_for(SOURCE)
    urls = profile_urls()
    if not urls:
        return {"no_x_handles": 1}
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
        session, store, posts, source=SOURCE, object_type="posts", notes=notes
    )
    return notes or None
