"""
Google Ads API mock provider.
Contract: seeds/docs/07-google-ads.md

Single POST searchStream endpoint. Returns all results in one response (no pagination).
Requires both Authorization: Bearer and developer-token headers.
"""

import re
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from seeds.helpers import require_bearer, require_header
from seeds.world import AD_CAMPAIGNS, COMPANIES_BY_ID

router = APIRouter()

_GADS_CAMPAIGNS = [ac for ac in AD_CAMPAIGNS if ac.platform == "google"]


class SearchStreamRequest(BaseModel):
    query: str


def _gads_error(code, message, status):
    return {"error": {"code": code, "message": message, "status": status}}


def _campaign_result(ac, day="2026-07-01"):
    return {
        "campaign": {
            "id": ac.id,
            "name": ac.name,
            "status": "ENABLED" if ac.status == "active" else "PAUSED",
            "advertisingChannelType": "SEARCH",
            "biddingStrategyType": "TARGET_CPA" if ac.conversions > 50 else "MAXIMIZE_CONVERSIONS",
        },
        "adGroup": {
            "id": f"ag_{ac.id[-3:]}",
            "name": f"{ac.name} - Ad Group",
            "status": "ENABLED" if ac.status == "active" else "PAUSED",
        },
        "metrics": {
            "costMicros": str(ac.spend_cents * 10000),
            "clicks": str(ac.clicks),
            "impressions": str(ac.impressions),
            "conversions": f"{ac.conversions}.0",
            "conversionsValue": f"{ac.conversions * 140:.2f}",
            "allConversions": f"{ac.conversions + 3}.0",
            "ctr": f"{ac.clicks / ac.impressions:.6f}" if ac.impressions else "0",
            "averageCpc": str(int(ac.spend_cents * 10000 / ac.clicks)) if ac.clicks else "0",
            "averageCpm": str(int(ac.spend_cents * 10000 / ac.impressions * 1000)) if ac.impressions else "0",
        },
        "segments": {"date": day},
    }


def _budget_result(ac):
    return {
        "campaign": {
            "id": ac.id,
            "name": ac.name,
            "status": "ENABLED" if ac.status == "active" else "PAUSED",
        },
        "campaignBudget": {
            "amountMicros": str(ac.daily_budget_cents * 10000),
            "type": "STANDARD",
        },
    }


def _keyword_result(ac, day="2026-07-01"):
    keyword = ac.name.lower().replace(" - ", " ").replace("-", " ")
    return {
        "adGroup": {"name": f"{ac.name} - Ad Group"},
        "adGroupCriterion": {
            "keyword": {"text": keyword, "matchType": "EXACT"},
            "qualityInfo": {
                "qualityScore": 9 if ac.conversions > 50 else 7,
                "creativeQualityScore": "ABOVE_AVERAGE",
                "postClickQualityScore": "ABOVE_AVERAGE" if ac.conversions > 50 else "AVERAGE",
                "searchPredictedCtr": "ABOVE_AVERAGE",
            },
        },
        "metrics": {
            "clicks": str(ac.clicks // 3),
            "impressions": str(ac.impressions // 5),
            "costMicros": str(ac.spend_cents * 10000 // 3),
        },
        "segments": {"date": day},
    }


def _detect_resource(query: str) -> str:
    q = query.lower()
    if "keyword_view" in q:
        return "keyword"
    if "geographic_view" in q:
        return "geo"
    if "search_term_view" in q:
        return "search_term"
    if "campaign_budget" in q:
        return "budget"
    if "segments.device" in q:
        return "device"
    return "campaign"


@router.post("/v24/customers/{customer_id}/googleAds:searchStream")
async def search_stream(request: Request, customer_id: str, body: SearchStreamRequest):
    require_bearer(request)
    require_header(request, "developer-token")

    query = body.query
    resource = _detect_resource(query)

    if resource == "campaign":
        results = [_campaign_result(ac) for ac in _GADS_CAMPAIGNS]
    elif resource == "budget":
        results = [_budget_result(ac) for ac in _GADS_CAMPAIGNS]
    elif resource == "keyword":
        results = [_keyword_result(ac) for ac in _GADS_CAMPAIGNS]
    elif resource == "device":
        results = []
        for ac in _GADS_CAMPAIGNS:
            for device, pct in [("MOBILE", 0.55), ("DESKTOP", 0.35), ("TABLET", 0.10)]:
                results.append({
                    "campaign": {"name": ac.name},
                    "metrics": {
                        "clicks": str(int(ac.clicks * pct)),
                        "impressions": str(int(ac.impressions * pct)),
                        "costMicros": str(int(ac.spend_cents * 10000 * pct)),
                    },
                    "segments": {"device": device, "date": "2026-07-01"},
                })
    elif resource == "geo":
        results = [
            {
                "geographicView": {"countryCriterionId": "2840", "locationType": "LOCATION_OF_PRESENCE"},
                "metrics": {"clicks": "2100", "impressions": "42000", "costMicros": "8500000000"},
                "segments": {"date": "2026-07-01"},
            },
            {
                "geographicView": {"countryCriterionId": "2826", "locationType": "LOCATION_OF_PRESENCE"},
                "metrics": {"clicks": "450", "impressions": "9800", "costMicros": "1800000000"},
                "segments": {"date": "2026-07-01"},
            },
        ]
    elif resource == "search_term":
        results = [
            {
                "searchTermView": {"searchTerm": "acme software reviews", "status": "ADDED"},
                "campaign": {"name": _GADS_CAMPAIGNS[0].name if _GADS_CAMPAIGNS else "Brand Search"},
                "metrics": {"clicks": "85", "impressions": "1200", "costMicros": "340000000"},
                "segments": {"date": "2026-07-01"},
            },
        ]
    else:
        results = []

    return [{"results": results}]
