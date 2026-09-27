from app.engine import spy
from app.sources import brightdata
from app.sources.util import client_for, store_all

SOURCE = "linkedin_posts"

OBSERVED_AT = {"posts": "date_posted"}

DATASET_ID = "gd_lyy3tktm25m4avu764"
DISCOVER_BY = "company_url"


def company_urls() -> list[str]:
    return [
        f"https://www.linkedin.com/company/{company.linkedin}"
        for company in spy.definition().competitors
        if company.linkedin
    ]


async def pull(session, store):
    api = client_for(SOURCE)
    urls = company_urls()
    if not urls:
        return {"no_linkedin_handles": 1}
    notes: dict = {}
    posts = []
    for record in await brightdata.discover(
        api, SOURCE, dataset_id=DATASET_ID, discover_by=DISCOVER_BY, urls=urls
    ):
        if brightdata.failed(record):
            notes["dead_pages"] = notes.get("dead_pages", 0) + 1
            continue
        posts.append(record)
    await store_all(
        session, store, posts, source=SOURCE, object_type="posts", notes=notes
    )
    return notes or None
