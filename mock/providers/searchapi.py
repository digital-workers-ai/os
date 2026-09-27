import base64
import hashlib
import json
from datetime import date
from urllib.parse import quote_plus

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from seeds import world
from seeds.helpers import day_ms, token_paginate

router = APIRouter()

NO_RESULTS = "LinkedIn Ad Library didn't return any results."
STAMP = f"{world.SPY_ANCHOR.isoformat()}T12:00:00Z"
ADS_PAGE = 24
AD_LIBRARY = "https://www.linkedin.com/ad-library"
DETAILS_ENGINE = "linkedin_ad_library_ad_details"
TIKTOK_ENGINE = "tiktok_ads_library"
TIKTOK_ADVERTISERS_ENGINE = "tiktok_ads_library_advertiser_search"
TIKTOK_NO_RESULTS = "TikTok ads library didn't return any results."
TIKTOK_NO_ADVERTISERS = (
    "TikTok ads library advertiser search didn't return any results."
)
TIKTOK_MISSING_Q = (
    "Missing required parameter q. When searching by advertiser_id, you must also "
    "provide the advertiser's name via q (or use advertiser_token, which bundles "
    "both). You can look up advertisers with the "
    "tiktok_ads_library_advertiser_search engine."
)
TIKTOK_LIBRARY = "https://library.tiktok.com/ads"
TIKTOK_PAGE = 12
TIKTOK_SORT = "last_shown_date_newest_to_oldest"
TIKTOK_PERIOD = (
    f"{world.SPY_ANCHOR.replace(year=world.SPY_ANCHOR.year - 1).isoformat()}"
    f"..{world.SPY_ANCHOR.isoformat()}"
)
META_ENGINE = "meta_ad_library"
META_PAGES_ENGINE = "meta_ad_library_page_search"
META_NO_RESULTS = "Meta Ad Library didn't return any results."
META_NO_PAGES = "Meta Ad Library page search didn't return any results."
META_LIBRARY = "https://www.facebook.com/ads/library"
META_PAGE = 30
META_SORT = "impressions_high_to_low"
META_PAGE_INFO = {
    "related_pages": [],
    "has_blank_ads": False,
    "hidden_ads": 0,
    "page_is_deleted": False,
}


def _error(status, message):
    return JSONResponse(status_code=status, content={"error": message})


def _missing(name):
    return _error(400, f"Missing required parameter {name}.")


def _metadata(seed, request_url):
    search_id = "search_" + hashlib.md5(seed.encode()).hexdigest()[:24]
    archive = f"https://www.searchapi.io/api/v1/searches/{search_id}"
    return {
        "id": search_id,
        "status": "Success",
        "created_at": STAMP,
        "request_time_taken": 1.2,
        "parsing_time_taken": 0.03,
        "total_time_taken": 1.23,
        "request_url": request_url,
        "html_url": f"{archive}.html",
        "json_url": archive,
    }


def _listing(body, ads, page_token, page_size, no_results):
    if not ads:
        body["error"] = no_results
        return body
    page, next_token = token_paginate(ads, page_token, page_size)
    body["search_information"] = {"total_results": len(ads)}
    body["ads"] = page
    if next_token:
        body["pagination"] = {"next_page_token": next_token}
    return body


def _ad_library(params):
    advertiser = params.get("advertiser")
    if not advertiser:
        return _missing("advertiser")
    country = params.get("country")
    page_token = params.get("next_page_token")
    echoed = {"engine": "linkedin_ad_library", "advertiser": advertiser}
    request_url = f"{AD_LIBRARY}/search?accountOwner={quote_plus(advertiser)}"
    if country:
        echoed["country"] = country
        request_url += f"&countries={country}"
    body = {
        "search_metadata": _metadata(
            f"ads|{advertiser}|{country}|{page_token}", request_url
        ),
        "search_parameters": echoed,
    }
    ads = world.spy_linkedin_ads(advertiser)
    return _listing(body, ads, page_token, ADS_PAGE, NO_RESULTS)


def _ad_details(params):
    ad_id = params.get("ad_id")
    if not ad_id:
        return _missing("ad_id")
    body = {
        "search_metadata": _metadata(f"ad|{ad_id}", f"{AD_LIBRARY}/detail/{ad_id}"),
        "search_parameters": {"engine": DETAILS_ENGINE, "ad_id": ad_id},
    }
    ad = world.spy_linkedin_ad_detail(ad_id)
    if ad is None:
        body["error"] = NO_RESULTS
    else:
        body["ad"] = ad
    return body


def _tiktok_ads(params):
    given = {
        key: params[key]
        for key in ("advertiser_token", "q", "advertiser_id")
        if key in params
    }
    if "advertiser_token" in given:
        advertiser = json.loads(base64.b64decode(given["advertiser_token"]))
        advertiser_id, name = advertiser["id"], advertiser["name"]
    else:
        advertiser_id, name = given.get("advertiser_id"), given.get("q")
        if not name:
            return _error(400, TIKTOK_MISSING_Q) if advertiser_id else _missing("q")
    country = params.get("country", "all")
    period = params.get("time_period", TIKTOK_PERIOD)
    page_token = params.get("next_page_token")
    start, end = (day_ms(date.fromisoformat(day)) for day in period.split(".."))
    request_url = (
        f"{TIKTOK_LIBRARY}?region={country}&start_time={start}&end_time={end}"
        f"&sort_type=last_shown_date%2Cdesc&adv_name={quote_plus(name)}"
        f"&adv_biz_ids={advertiser_id or ''}&query_type={2 if advertiser_id else 1}"
    )
    if advertiser_id:
        ads = [
            a for a in world.spy_tiktok_ads(advertiser_id) if a["advertiser"] == name
        ]
    else:
        ads = [
            ad
            for found in world.spy_tiktok_advertisers(name)
            for ad in world.spy_tiktok_ads(found["id"])
        ]
    body = {
        "search_metadata": _metadata(
            f"tiktok|{advertiser_id}|{name}|{country}|{period}|{page_token}",
            request_url,
        ),
        "search_parameters": {
            "engine": TIKTOK_ENGINE,
            **given,
            "country": country,
            "time_period": period,
            "sort_by": params.get("sort_by", TIKTOK_SORT),
        },
    }
    return _listing(body, ads, page_token, TIKTOK_PAGE, TIKTOK_NO_RESULTS)


def _tiktok_advertisers(params):
    query = params.get("q")
    if not query:
        return _missing("q")
    body = {
        "search_metadata": _metadata(f"tiktok_advertisers|{query}", TIKTOK_LIBRARY),
        "search_parameters": {"engine": TIKTOK_ADVERTISERS_ENGINE, "q": query},
    }
    advertisers = world.spy_tiktok_advertisers(query)
    if advertisers:
        body["advertisers"] = advertisers
    else:
        body["error"] = TIKTOK_NO_ADVERTISERS
    return body


def _meta_ads(params):
    page_id = params.get("page_id")
    if not page_id:
        return _missing("page_id")
    country = params.get("country", "ALL")
    status = params.get("active_status", "active")
    media_type = params.get("media_type", "all")
    sort_by = params.get("sort_by", META_SORT)
    page_token = params.get("next_page_token")
    request_url = (
        f"{META_LIBRARY}/?active_status={status}&ad_type=all&country={country}"
        f"&media_type={media_type}&view_all_page_id={page_id}"
        f"&sort_data[direction]=desc&sort_data[mode]={sort_by}"
    )
    body = {
        "search_metadata": _metadata(
            f"meta|{page_id}|{country}|{status}|{media_type}|{sort_by}|{page_token}",
            request_url,
        ),
        "search_parameters": {
            "engine": META_ENGINE,
            "page_id": page_id,
            "country": country,
            "active_status": status,
            "media_type": media_type,
            "sort_by": sort_by,
        },
    }
    ads = world.spy_meta_ads(page_id)
    listing = _listing(body, ads, page_token, META_PAGE, META_NO_RESULTS)
    if ads:
        listing["search_information"].update(
            ad_library_page_info=META_PAGE_INFO,
            page={"name": ads[0]["page_name"], "id": page_id},
        )
    return listing


def _meta_pages(params):
    query = params.get("q")
    if not query:
        return _missing("q")
    body = {
        "search_metadata": _metadata(f"meta_pages|{query}", META_LIBRARY),
        "search_parameters": {"engine": META_PAGES_ENGINE, "q": query},
    }
    pages = world.spy_meta_pages(query)
    if pages:
        body["page_results"] = pages
    else:
        body["error"] = META_NO_PAGES
    return body


ENGINES = {
    "linkedin_ad_library": _ad_library,
    DETAILS_ENGINE: _ad_details,
    TIKTOK_ENGINE: _tiktok_ads,
    TIKTOK_ADVERTISERS_ENGINE: _tiktok_advertisers,
    META_ENGINE: _meta_ads,
    META_PAGES_ENGINE: _meta_pages,
}


@router.get("/api/v1/search")
async def search(request: Request):
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer ") or len(auth) == 7:
        return _error(401, "Invalid API key")
    params = dict(request.query_params)
    engine = params.get("engine")
    if not engine:
        return _missing("engine")
    handler = ENGINES.get(engine)
    if handler is None:
        return _error(400, f"Unsupported engine: `{engine}`.")
    return handler(params)
