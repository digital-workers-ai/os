import json

from app.engine import competitors
from app.sources.util import client_for, store_all

SOURCE = "meta_ad_library"

OBSERVED_AT: dict = {}

PAGE_FIELDS = "id,name,website"

AD_FIELDS = (
    "id,page_id,page_name,ad_creative_bodies,ad_creative_link_titles,"
    "ad_snapshot_url,publisher_platforms,ad_delivery_start_time,"
    "ad_delivery_stop_time"
)

COUNTRIES = json.dumps(["US"])


async def pull(session, store):
    api = client_for(SOURCE)
    notes: dict = {}
    for spec in competitors.tracked().values():
        page_id = str(spec["meta_page_id"])
        page = await api.get(f"/v25.0/{page_id}", params={"fields": PAGE_FIELDS})
        await store_all(
            session, store, [page], source=SOURCE, object_type="pages", notes=notes
        )
        ads = await api.get(
            "/v25.0/ads_archive",
            params={
                "search_page_ids": page_id,
                "ad_active_status": "ALL",
                "ad_reached_countries": COUNTRIES,
                "fields": AD_FIELDS,
                "limit": 100,
            },
            paginate="cursor_meta",
        )
        await store_all(
            session, store, ads, source=SOURCE, object_type="ads", notes=notes
        )
    return notes or None
