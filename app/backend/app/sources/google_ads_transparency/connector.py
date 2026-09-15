from app.engine import competitors
from app.sources.util import client_for, store_all

SOURCE = "google_ads_transparency"

OBSERVED_AT: dict = {}

ENGINE = "google_ads_transparency_center"


def _advertiser(advertiser_id, creatives):
    if not creatives:
        return {"id": advertiser_id}
    first = creatives[0]
    return {
        "id": advertiser_id,
        "name": first.get("advertiser"),
        "domain": first.get("target_domain"),
    }


async def pull(session, store):
    api = client_for(SOURCE)
    notes: dict = {}
    for spec in competitors.tracked().values():
        advertiser_id = str(spec["google_advertiser_id"])
        creatives = await api.get(
            "/search",
            params={"engine": ENGINE, "advertiser_id": advertiser_id},
            paginate="token_serpapi",
        )
        await store_all(
            session,
            store,
            creatives,
            source=SOURCE,
            object_type="creatives",
            id_fields=("ad_id",),
            notes=notes,
        )
        await store_all(
            session,
            store,
            [_advertiser(advertiser_id, creatives)],
            source=SOURCE,
            object_type="advertisers",
            notes=notes,
        )
    return notes or None
