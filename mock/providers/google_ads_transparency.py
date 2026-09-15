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
_SIZES = {"text": (300, 250), "image": (1200, 628), "video": (1280, 720)}
_DETAILS_ENGINE = "google_ads_transparency_center_details"


def _unix(day):
    return day_ms(date.fromisoformat(day)) // 1000


def _days_shown(started, stopped):
    return (date.fromisoformat(stopped) - date.fromisoformat(started)).days + 1


def _creative(competitor, ad):
    creative_id = f"CR3041{ad.id[2:].zfill(16)}"
    advertiser_id = competitor.google_advertiser_id
    stopped = ad.stopped or _LAST_SHOWN_WHEN_RUNNING
    width, height = _SIZES[ad.format]
    record = {
        "advertiser_id": advertiser_id,
        "advertiser": competitor.name,
        "ad_creative_id": creative_id,
        "format": ad.format,
        "width": width,
        "height": height,
        "first_shown": _unix(ad.started),
        "last_shown": _unix(stopped),
        "total_days_shown": _days_shown(ad.started, stopped),
        "details_link": f"https://adstransparency.google.com/advertiser/{advertiser_id}/creative/{creative_id}?region=anywhere",
        "serpapi_details_link": f"https://serpapi.com/search.json?engine={_DETAILS_ENGINE}&advertiser_id={advertiser_id}&creative_id={creative_id}",
    }
    if ad.format == "image":
        record["image"] = f"https://tpc.googlesyndication.com/archive/simgad/{creative_id[2:]}"
    else:
        record["target_domain"] = competitor.domain
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
