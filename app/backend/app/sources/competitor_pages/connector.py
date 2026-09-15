from app import clock
from app.engine import competitors
from app.sources.util import client_for, store_all

SOURCE = "competitor_pages"

OBSERVED_AT = {"pages": "_fetched_at"}

MAP_LIMIT = 50

MAP = {"includeSubdomains": False}

SCRAPE = {"formats": ["markdown"], "onlyMainContent": True}


def _source_url(page):
    return (page.get("metadata") or {}).get("sourceURL")


def _page(scraped, domain):
    data = scraped.get("data")
    if not scraped.get("success") or not isinstance(data, dict):
        return None
    return {**data, "_fetched_at": clock.now().isoformat(), "_competitor_ref": domain}


async def pull(session, store):
    api = client_for(SOURCE)
    notes: dict = {}
    for spec in competitors.tracked().values():
        domain = str(spec["domain"])
        mapped = await api.post(
            "/v2/map",
            json={"url": f"https://{domain}", "limit": MAP_LIMIT, **MAP},
        )
        pages = []
        for link in mapped.get("links") or []:
            scraped = await api.post("/v2/scrape", json={"url": link["url"], **SCRAPE})
            page = _page(scraped, domain)
            if page is None:
                notes["failed_scrapes"] = notes.get("failed_scrapes", 0) + 1
                continue
            pages.append(page)
        await store_all(
            session,
            store,
            pages,
            source=SOURCE,
            object_type="pages",
            id_of=_source_url,
            notes=notes,
        )
    return notes or None
