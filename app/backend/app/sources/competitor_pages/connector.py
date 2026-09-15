from urllib.parse import urlsplit

from app import clock
from app.engine import competitors
from app.sources.util import client_for, store_all

SOURCE = "competitor_pages"

OBSERVED_AT = {"pages": "_fetched_at"}

MAP_LIMIT = 50

SCRAPE = {"formats": ["markdown"], "onlyMainContent": True}


def _host(url):
    return (urlsplit(str(url or "")).hostname or "").removeprefix("www.")


def _source_url(page):
    return (page.get("metadata") or {}).get("sourceURL")


def _page(scraped):
    data = scraped.get("data")
    if not scraped.get("success") or not isinstance(data, dict):
        return None
    return {
        **data,
        "_fetched_at": clock.now().isoformat(),
        "_competitor_ref": _host(_source_url(data)),
    }


async def pull(session, store):
    api = client_for(SOURCE)
    notes: dict = {}
    for spec in competitors.tracked().values():
        mapped = await api.post(
            "/v2/map", json={"url": f"https://{spec['domain']}", "limit": MAP_LIMIT}
        )
        pages = []
        for link in mapped.get("links") or []:
            scraped = await api.post("/v2/scrape", json={"url": link["url"], **SCRAPE})
            page = _page(scraped)
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
