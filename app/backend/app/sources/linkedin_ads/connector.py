from app.engine import spy
from app.sources.searchapi import SEARCH_PATH, TokenPage
from app.sources.util import client_for, pick_id, store_all, stored_ids

SOURCE = "linkedin_ads"

OBSERVED_AT = {"ad_details": "ad.last_shown_date"}

ENGINE = "linkedin_ad_library"
DETAILS_ENGINE = "linkedin_ad_library_ad_details"
PAGES_PER_ADVERTISER = 2
DETAILS_PER_PULL = 50


def _ad_id(record):
    return pick_id(record["ad"], "id")


def _advertiser(item) -> str:
    advertiser = item.get("advertiser") if isinstance(item, dict) else None
    name = advertiser.get("name") if isinstance(advertiser, dict) else None
    return name.lower() if isinstance(name, str) else ""


def _company_by_ad(ads) -> dict:
    by_ad = {}
    for record in ads:
        ad_id = _ad_id(record)
        if ad_id:
            by_ad[ad_id] = record["request"]["company"]
    return by_ad


async def _read_details(session, store, api, ads, notes):
    by_ad = _company_by_ad(ads)
    already = await stored_ids(session, SOURCE, "ad_details")
    fresh = [ad_id for ad_id in by_ad if ad_id not in already]
    skipped = len(by_ad) - len(fresh)
    if skipped:
        notes["ad_details_skipped"] = skipped
    if len(fresh) > DETAILS_PER_PULL:
        notes["ad_details_capped"] = len(fresh) - DETAILS_PER_PULL
    read = 0
    for ad_id in fresh[:DETAILS_PER_PULL]:
        data = await api.get(
            SEARCH_PATH, params={"engine": DETAILS_ENGINE, "ad_id": ad_id}
        )
        detail = data.get("ad") if isinstance(data, dict) else None
        if not isinstance(detail, dict):
            notes["ad_details_missing"] = notes.get("ad_details_missing", 0) + 1
            continue
        await store(
            session,
            source=SOURCE,
            object_type="ad_details",
            source_id=ad_id,
            raw_payload={
                "request": {"company": by_ad[ad_id], "ad_id": ad_id},
                "ad": detail,
            },
        )
        read += 1
    if read:
        notes["ad_details_read"] = read


async def pull(session, store):
    api = client_for(SOURCE)
    definition = spy.definition()
    notes: dict = {}
    ads = []
    for company in definition.competitors:
        walk = TokenPage("ads", PAGES_PER_ADVERTISER)
        page = await api.get(
            SEARCH_PATH,
            params={
                "engine": ENGINE,
                "advertiser": company.name,
                "country": definition.country,
            },
            paginate=walk,
        )
        if walk.more:
            notes["ads_capped"] = notes.get("ads_capped", 0) + 1
        names = {name.lower() for name in company.names}
        for item in page:
            if _advertiser(item) not in names:
                notes["ads_foreign_advertiser"] = (
                    notes.get("ads_foreign_advertiser", 0) + 1
                )
                continue
            ads.append(
                {
                    "request": {"company": company.name, "advertiser": company.name},
                    "ad": item,
                }
            )
    await store_all(
        session,
        store,
        ads,
        source=SOURCE,
        object_type="ads",
        id_of=_ad_id,
        notes=notes,
    )
    await _read_details(session, store, api, ads, notes)
    return notes or None
