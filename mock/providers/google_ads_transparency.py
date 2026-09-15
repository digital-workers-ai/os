from datetime import date

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from seeds.helpers import day_ms, token_paginate
from seeds.world import COMPETITOR_ADS_BY_COMPETITOR, COMPETITORS

router = APIRouter()

_ENGINE = "google_ads_transparency_center"
_ADVERTISERS = {k.google_advertiser_id: k for k in COMPETITORS}
_LAST_SHOWN_WHEN_RUNNING = "2026-09-03"
_PAGE_SIZE = 1


def _unix(day):
    return day_ms(date.fromisoformat(day)) // 1000


def _creative(competitor, ad):
    ad_id = f"CR3041{ad.id[2:].zfill(16)}"
    record = {
        "advertiser_id": competitor.google_advertiser_id,
        "advertiser": competitor.name,
        "ad_id": ad_id,
        "format": ad.format,
        "link": f"https://adstransparency.google.com/advertiser/{competitor.google_advertiser_id}/creative/{ad_id}",
        "target_domain": competitor.domain,
        "first_shown": _unix(ad.started),
        "last_shown": _unix(ad.stopped or _LAST_SHOWN_WHEN_RUNNING),
    }
    if ad.format == "text":
        record["text"] = ad.body
    elif ad.format == "image":
        record["image"] = f"https://tpc.googlesyndication.com/archive/simgad/{ad_id[2:]}"
    else:
        record["video"] = f"https://www.youtube.com/embed/{ad_id}"
    return record


def _creatives(competitor, creative_format):
    return [
        _creative(competitor, ad)
        for ad in COMPETITOR_ADS_BY_COMPETITOR[competitor.id]
        if ad.platform == "google" and (creative_format is None or ad.format == creative_format)
    ]


@router.get("/search")
async def search(
    request: Request,
    engine: str = Query(...),
    advertiser_id: str = Query(None),
    creative_format: str = Query(None),
    next_page_token: str = Query(None),
):
    if not request.query_params.get("api_key"):
        return JSONResponse(
            status_code=401,
            content={"error": "Invalid API key. Your API key should be here: https://serpapi.com/manage-api-key"},
        )
    if engine != _ENGINE:
        return JSONResponse(status_code=400, content={"error": f"Unsupported `{engine}` engine."})
    competitor = _ADVERTISERS.get(advertiser_id)
    if competitor is None:
        return {"error": "Google hasn't returned any results for this query."}
    page, next_token = token_paginate(_creatives(competitor, creative_format), next_page_token, _PAGE_SIZE)
    return {
        "search_metadata": {"status": "Success"},
        "search_parameters": {"engine": engine, "advertiser_id": advertiser_id},
        "ad_creatives": page,
        "serpapi_pagination": {"next_page_token": next_token} if next_token else {},
    }
