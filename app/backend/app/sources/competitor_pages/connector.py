from app.engine import competitors
from app.sources.util import client_for, store_all

SOURCE = "competitor_pages"

OBSERVED_AT = {"pages": "fetched_at"}


async def pull(session, store):
    api = client_for(SOURCE)
    notes: dict = {}
    for spec in competitors.tracked().values():
        sitemap = await api.get("/v1/sitemap", params={"domain": str(spec["domain"])})
        pages = [
            await api.get("/v1/fetch", params={"url": url})
            for url in sitemap.get("urls") or []
        ]
        await store_all(
            session,
            store,
            pages,
            source=SOURCE,
            object_type="pages",
            id_fields=("url",),
            notes=notes,
        )
    return notes or None
