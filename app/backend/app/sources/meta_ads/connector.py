from app.engine import spy
from app.sources.searchapi import SEARCH_PATH, TokenPage
from app.sources.util import client_for, pick_id, store_all

SOURCE = "meta_ads"

OBSERVED_AT = {"ads": "ad.end_date"}

ENGINE = "meta_ad_library"
PAGES_PER_PAGE = 2
STATUS = "all"
SORT = "most_recent"


def _ad_id(record):
    return pick_id(record["ad"], "ad_archive_id")


async def pull(session, store):
    definition = spy.definition()
    pages = [c for c in definition.competitors if c.meta_page_id]
    if not pages:
        return {"no_meta_pages": 1}
    api = client_for(SOURCE)
    notes: dict = {}
    ads = []
    for company in pages:
        walk = TokenPage("ads", PAGES_PER_PAGE)
        page = await api.get(
            SEARCH_PATH,
            params={
                "engine": ENGINE,
                "page_id": company.meta_page_id,
                "country": definition.country,
                "active_status": STATUS,
                "sort_by": SORT,
            },
            paginate=walk,
        )
        if walk.more:
            notes["ads_capped"] = notes.get("ads_capped", 0) + 1
        ads += [
            {
                "request": {"company": company.name, "page_id": company.meta_page_id},
                "ad": item,
            }
            for item in page
        ]
    await store_all(
        session,
        store,
        ads,
        source=SOURCE,
        object_type="ads",
        id_of=_ad_id,
        notes=notes,
    )
    return notes or None
