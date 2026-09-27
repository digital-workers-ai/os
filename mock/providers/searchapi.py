import hashlib
from urllib.parse import quote_plus

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from seeds import world
from seeds.helpers import token_paginate

router = APIRouter()

NO_RESULTS = "LinkedIn Ad Library didn't return any results."
STAMP = f"{world.SPY_ANCHOR.isoformat()}T12:00:00Z"
ADS_PAGE = 24
AD_LIBRARY = "https://www.linkedin.com/ad-library"
DETAILS_ENGINE = "linkedin_ad_library_ad_details"


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
    if not ads:
        body["error"] = NO_RESULTS
        return body
    page, next_token = token_paginate(ads, page_token, ADS_PAGE)
    body["search_information"] = {"total_results": len(ads)}
    body["ads"] = page
    if next_token:
        body["pagination"] = {"next_page_token": next_token}
    return body


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


@router.get("/api/v1/search")
async def search(request: Request):
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer ") or len(auth) == 7:
        return _error(401, "Invalid API key")
    params = dict(request.query_params)
    engine = params.get("engine")
    if not engine:
        return _missing("engine")
    if engine == "linkedin_ad_library":
        return _ad_library(params)
    if engine == DETAILS_ENGINE:
        return _ad_details(params)
    return _error(400, f"Unsupported engine: `{engine}`.")
