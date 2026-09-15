from app.engine import competitors
from app.sources.util import client_for, store_all

SOURCE = "linkedin_posts"

OBSERVED_AT: dict = {}


async def pull(session, store):
    api = client_for(SOURCE)
    notes: dict = {}
    for spec in competitors.tracked().values():
        domain = str(spec["domain"])
        answer = await api.get("/v1/posts", params={"domain": domain})
        posts = [{**post, "_domain": domain} for post in answer.get("posts") or []]
        await store_all(
            session, store, posts, source=SOURCE, object_type="posts", notes=notes
        )
    return notes or None
