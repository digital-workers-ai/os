import base64
import binascii
import hashlib
from urllib.parse import quote_plus, urlencode

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from seeds.helpers import token_paginate
from seeds.world import (
    SPY_ANCHOR,
    SPY_COMPETITORS,
    spy_ads,
    spy_ai_overview,
    spy_ai_overview_mode,
    spy_serp,
)

router = APIRouter()

INVALID_KEY = (
    "Invalid API key. Your API key should be here: https://serpapi.com/manage-api-key"
)
NO_RESULTS = "Google hasn't returned any results for this query."
OVERVIEW_UNAVAILABLE = "Can't generate an AI overview right now. Try again later."
STAMP = f"{SPY_ANCHOR.isoformat()} 12:00:00 UTC"
ADS_PAGE = 40
PREVIEW = "https://displayads-formats.googleusercontent.com/ads/preview/content.js"
TRANSPARENCY = "https://adstransparency.google.com"
DETAILS_ENGINE = "google_ads_transparency_center_ad_details"


def _error(status, message):
    return JSONResponse(status_code=status, content={"error": message})


def _metadata(seed, page_key, page_url, pixel_position=False, prettify=False):
    search_id = hashlib.md5(seed.encode()).hexdigest()[:24]
    archive = f"https://serpapi.com/searches/{search_id}"
    metadata = {
        "id": search_id,
        "status": "Success",
        "json_endpoint": f"{archive}.json",
        "markdown_endpoint": f"{archive}.md",
    }
    if pixel_position:
        metadata["pixel_position_endpoint"] = f"{archive}.json_with_pixel_position"
    metadata["created_at"] = STAMP
    metadata["processed_at"] = STAMP
    metadata[page_key] = page_url
    metadata["raw_html_file"] = f"{archive}.html"
    if prettify:
        metadata["prettify_html_file"] = f"{archive}.prettify"
    metadata["total_time_taken"] = 0.5
    return metadata


def _link(request, params):
    return str(request.url.replace(query=urlencode(params)))


def _page_token(q):
    return base64.urlsafe_b64encode(q.encode()).decode()


def _query_of(page_token):
    try:
        return base64.urlsafe_b64decode(page_token.encode()).decode()
    except (binascii.Error, UnicodeDecodeError):
        return None


def _google(request, params):
    q = params.get("q")
    if not q:
        return _error(400, "Missing query `q` parameter.")
    hl = params.get("hl", "en")
    gl = params.get("gl", "us")
    google_url = (
        f"https://www.google.com/search?q={quote_plus(q)}&oq={quote_plus(q)}"
        f"&hl={hl}&gl={gl}&sourceid=chrome&ie=UTF-8"
    )
    body = {
        "search_metadata": _metadata(
            f"google|{q}|{gl}|{hl}", "google_url", google_url, pixel_position=True
        ),
        "search_parameters": {
            "engine": "google",
            "q": q,
            "google_domain": "google.com",
            "hl": hl,
            "gl": gl,
            "device": "desktop",
        },
        "search_information": {
            "query_displayed": q,
            "total_results": 100_000 + int(hashlib.md5(q.encode()).hexdigest()[:6], 16),
            "time_taken_displayed": 0.14,
            "organic_results_state": "Results for exact spelling",
        },
    }
    mode = spy_ai_overview_mode(q)
    if mode == "inline":
        body["ai_overview"] = spy_ai_overview(q)
    elif mode == "token":
        token = _page_token(q)
        follow_up = {"engine": "google_ai_overview", "page_token": token}
        body["ai_overview"] = {
            "page_token": token,
            "serpapi_link": _link(request, follow_up),
        }
    body["organic_results"] = spy_serp(q)
    return body


def _google_ai_overview(params):
    token = params.get("page_token")
    if not token:
        return _error(400, "Missing query `page_token` parameter.")
    q = _query_of(token)
    overview = spy_ai_overview(q) if q else None
    if overview is None:
        overview = {"error": OVERVIEW_UNAVAILABLE}
    page_url = f"https://www.google.com/async/callback:6761?fc={quote_plus(token)}"
    return {
        "search_metadata": _metadata(
            f"google_ai_overview|{token}", "google_ai_overview_url", page_url
        ),
        "search_parameters": {"engine": "google_ai_overview", "page_token": token},
        "ai_overview": overview,
    }


def _company_for_text(text):
    needle = text.lower()
    for company in SPY_COMPETITORS:
        names = [company["name"], *company["aliases"]]
        if needle == company["domain"] or any(needle in n.lower() for n in names):
            return company
    return None


def _company_for_id(advertiser_id):
    for company in SPY_COMPETITORS:
        if company["google_advertiser_id"] == advertiser_id:
            return company
    return None


def _creative(company, creative, text_search):
    advertiser_id = company["google_advertiser_id"]
    creative_id = creative["ad_creative_id"]
    item = {
        "advertiser_id": advertiser_id,
        "advertiser": company["name"],
        "ad_creative_id": creative_id,
        "format": creative["format"],
    }
    if text_search:
        item["target_domain"] = company["domain"]
    if creative["format"] == "video":
        item["link"] = (
            f"{PREVIEW}?client=ads-integrity-transparency&creativeId={creative_id[2:14]}"
        )
    else:
        item["image"] = creative["image"]
        item["width"] = creative["width"]
        item["height"] = creative["height"]
    shown_for = creative["last_shown"] - creative["first_shown"]
    item["total_days_shown"] = shown_for // 86_400 + 1
    item["first_shown"] = creative["first_shown"]
    item["last_shown"] = creative["last_shown"]
    item["details_link"] = creative["details_link"]
    item["serpapi_details_link"] = (
        f"https://serpapi.com/search.json?advertiser_id={advertiser_id}"
        f"&creative_id={creative_id}&engine={DETAILS_ENGINE}"
    )
    return item


def _ads_transparency(request, params):
    advertiser_id = params.get("advertiser_id")
    text = params.get("text")
    if not advertiser_id and not text:
        return _error(400, "Missing query `advertiser_id` parameter.")
    num = int(params.get("num", ADS_PAGE))
    page_token = params.get("next_page_token")
    echoed = {"engine": "google_ads_transparency_center"}
    if advertiser_id:
        company = _company_for_id(advertiser_id)
        echoed["advertiser_id"] = advertiser_id
        page_url = f"{TRANSPARENCY}/advertiser/{advertiser_id}?region=anywhere"
    else:
        company = _company_for_text(text)
        echoed["text"] = text
        page_url = f"{TRANSPARENCY}?region=anywhere&domain={quote_plus(text)}"
    if page_token:
        echoed["next_page_token"] = page_token
    echoed["num"] = str(num)
    body = {
        "search_metadata": _metadata(
            f"ads|{advertiser_id or text}|{page_token or ''}",
            "google_ads_transparency_center_url",
            page_url,
            prettify=True,
        ),
        "search_parameters": echoed,
    }
    if company is None:
        body["error"] = NO_RESULTS
        return body
    creatives = [
        _creative(company, creative, text_search=not advertiser_id)
        for creative in spy_ads(company["google_advertiser_id"])
    ]
    page, next_token = token_paginate(creatives, page_token, num)
    body["search_information"] = {"total_results": len(creatives)}
    body["ad_creatives"] = page
    if next_token:
        following = dict(echoed, next_page_token=next_token)
        body["serpapi_pagination"] = {
            "next_page_token": next_token,
            "next": _link(request, dict(sorted(following.items()))),
        }
    return body


@router.get("/search.json")
@router.get("/search")
async def search(request: Request):
    params = dict(request.query_params)
    if not params.get("api_key"):
        return _error(401, INVALID_KEY)
    engine = params.get("engine", "google")
    if engine == "google":
        return _google(request, params)
    if engine == "google_ai_overview":
        return _google_ai_overview(params)
    if engine == "google_ads_transparency_center":
        return _ads_transparency(request, params)
    return _error(400, f"Unsupported `{engine}` search engine.")
