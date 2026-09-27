from app.engine import spy
from app.sources.searchapi import SEARCH_PATH, TokenPage
from app.sources.util import client_for, pick_id, store_all

SOURCE = "tiktok_ads"

OBSERVED_AT = {"ads": "ad.last_shown_datetime"}

ENGINE = "tiktok_ads_library"
PAGES_PER_ADVERTISER = 4
SORT = "last_shown_date_newest_to_oldest"


def _ad_id(record):
    return pick_id(record["ad"], "id")


async def pull(session, store):
    definition = spy.definition()
    advertisers = [c for c in definition.competitors if c.tiktok_advertiser_id]
    if not advertisers:
        return {"no_tiktok_advertisers": 1}
    api = client_for(SOURCE)
    notes: dict = {}
    ads = []
    for company in advertisers:
        walk = TokenPage("ads", PAGES_PER_ADVERTISER)
        page = await api.get(
            SEARCH_PATH,
            params={
                "engine": ENGINE,
                "advertiser_id": company.tiktok_advertiser_id,
                "q": company.tiktok_advertiser_name,
                "country": definition.country,
                "sort_by": SORT,
            },
            paginate=walk,
        )
        if walk.more:
            notes["ads_capped"] = notes.get("ads_capped", 0) + 1
        ads += [
            {
                "request": {
                    "company": company.name,
                    "advertiser_id": company.tiktok_advertiser_id,
                },
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
