from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from seeds.helpers import cursor_paginate, require_query_token
from seeds.world import COMPETITOR_ADS, COMPETITORS, COMPETITORS_BY_ID

router = APIRouter()

_PAGES = {k.meta_page_id: k for k in COMPETITORS}
_ARCHIVE = [ad for ad in COMPETITOR_ADS if ad.platform == "meta"]


def _archive_ad(ad, token):
    competitor = COMPETITORS_BY_ID[ad.competitor_id]
    ad_id = f"3041{ad.id[2:].zfill(11)}"
    record = {
        "id": ad_id,
        "page_id": competitor.meta_page_id,
        "page_name": competitor.name,
        "ad_creative_bodies": [ad.body],
        "ad_creative_link_titles": [ad.headline],
        "ad_snapshot_url": f"https://www.facebook.com/ads/archive/render_ad/?id={ad_id}&access_token={token}",
        "publisher_platforms": ["facebook", "instagram"],
        "ad_delivery_start_time": ad.started,
    }
    if ad.stopped:
        record["ad_delivery_stop_time"] = ad.stopped
    return record


def _requested(record, fields):
    wanted = {f.strip() for f in fields.split(",")}
    return {k: v for k, v in record.items() if k == "id" or k in wanted}


def _page_ids(search_page_ids):
    return {p.strip(' "[]') for p in search_page_ids.split(",")}


def _delivering(ad, ad_active_status):
    if ad_active_status == "ACTIVE":
        return ad.stopped is None
    if ad_active_status == "INACTIVE":
        return ad.stopped is not None
    return True


def _not_found(page_id):
    return JSONResponse(
        status_code=404,
        content={
            "error": {
                "message": f"Unsupported get request. Object with ID '{page_id}' does not exist, cannot be loaded due to missing permissions, or does not support this operation.",
                "type": "GraphMethodException",
                "code": 100,
            }
        },
    )


@router.get("/v25.0/ads_archive")
async def ads_archive(
    request: Request,
    search_page_ids: str = Query(...),
    ad_reached_countries: str = Query(...),
    ad_active_status: str = Query("ACTIVE"),
    fields: str = Query("id,ad_snapshot_url"),
    limit: int = Query(25, ge=1, le=1000),
    after: str = Query(None),
):
    token = require_query_token(request)
    page_ids = _page_ids(search_page_ids)
    ads = [
        _requested(_archive_ad(ad, token), fields)
        for ad in _ARCHIVE
        if COMPETITORS_BY_ID[ad.competitor_id].meta_page_id in page_ids
        and _delivering(ad, ad_active_status)
    ]
    page, next_cursor = cursor_paginate(ads, after, limit)
    result = {
        "data": page,
        "paging": {"cursors": {"before": "MAZDZD", "after": next_cursor or "MjQZD"}},
    }
    if next_cursor:
        result["paging"]["next"] = f"https://graph.facebook.com/v25.0/ads_archive?after={next_cursor}"
    return result


@router.get("/v25.0/{page_id}")
async def page(request: Request, page_id: str, fields: str = Query("id,name")):
    require_query_token(request)
    competitor = _PAGES.get(page_id)
    if competitor is None:
        return _not_found(page_id)
    record = {"id": page_id, "name": competitor.name, "website": f"https://{competitor.domain}"}
    return _requested(record, fields)
