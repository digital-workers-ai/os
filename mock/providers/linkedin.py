"""
LinkedIn Marketing API mock provider.
Contract: seeds/docs/13-linkedin-ads.md

Bearer auth + required Linkedin-Version header.
Cursor pagination (pageSize/pageToken) on adAccounts and adCampaigns.
"""

from fastapi import APIRouter, Request, Query
from seeds.helpers import require_bearer, require_header, token_paginate
from seeds.world import AD_CAMPAIGNS

router = APIRouter()

_LI_ADS = [ac for ac in AD_CAMPAIGNS if ac.platform == "linkedin"]

_AD_ACCOUNTS = [
    {
        "id": 512345678,
        "name": "Acme Corp - Marketing",
        "status": "ACTIVE",
        "type": "BUSINESS",
        "currency": "USD",
        "reference": "urn:li:organization:12345",
        "servingStatuses": ["RUNNABLE"],
        "totalBudget": {"amount": "50000.00", "currencyCode": "USD"},
        "created": 1710500000000,
        "lastModified": 1720000000000,
    },
    {
        "id": 512345679,
        "name": "Globex Inc - Lead Gen",
        "status": "ACTIVE",
        "type": "BUSINESS",
        "currency": "USD",
        "reference": "urn:li:organization:67890",
        "servingStatuses": ["RUNNABLE"],
        "totalBudget": {"amount": "25000.00", "currencyCode": "USD"},
        "created": 1715000000000,
        "lastModified": 1720500000000,
    },
    {
        "id": 512345680,
        "name": "Hooli - Enterprise",
        "status": "ACTIVE",
        "type": "BUSINESS",
        "currency": "USD",
        "reference": "urn:li:organization:11111",
        "servingStatuses": ["RUNNABLE"],
        "totalBudget": {"amount": "100000.00", "currencyCode": "USD"},
        "created": 1712000000000,
        "lastModified": 1720500000000,
    },
]


def _li_auth(request: Request):
    require_bearer(request)
    require_header(request, "linkedin-version")
    require_header(request, "x-restli-protocol-version")


def _li_campaign(ac):
    return {
        "id": int(ac.id.replace("ad", "6123450")),
        "name": ac.name,
        "account": f"urn:li:sponsoredAccount:512345678",
        "status": "ACTIVE" if ac.status == "active" else "PAUSED",
        "type": "SPONSORED_UPDATES",
        "costType": "CPC" if ac.objective == "LEAD_GENERATION" else "CPM",
        "objectiveType": ac.objective.upper().replace(" ", "_"),
        "dailyBudget": {"amount": f"{ac.daily_budget_cents / 100:.2f}", "currencyCode": "USD"},
        "totalBudget": {"amount": f"{ac.daily_budget_cents * 30 / 100:.2f}", "currencyCode": "USD"},
        "runSchedule": {"start": 1719792000000, "end": 1727654400000},
        "unitCost": {"amount": "12.50", "currencyCode": "USD"},
        "targeting": {
            "includedTargetingFacets": {
                "locations": ["urn:li:geo:103644278"],
                "interfaceLocales": [{"country": "US", "language": "en"}],
                "jobFunctions": ["urn:li:function:12"],
                "seniorities": ["urn:li:seniority:8", "urn:li:seniority:9"],
            }
        },
        "creativeSelection": "OPTIMIZED",
        "created": 1719700000000,
        "lastModified": 1720500000000,
    }


@router.get("/adAccounts")
async def list_ad_accounts(
    request: Request,
    q: str = Query("search"),
    pageSize: int = Query(100, ge=1, le=1000),
    pageToken: str = Query(None),
):
    _li_auth(request)
    page, next_token = token_paginate(_AD_ACCOUNTS, pageToken, pageSize)
    return {"elements": page, "metadata": {"nextPageToken": next_token}}


@router.get("/adAccounts/{ad_account_id}/adCampaigns")
async def list_campaigns(
    request: Request,
    ad_account_id: int,
    q: str = Query("search"),
    pageSize: int = Query(100, ge=1, le=1000),
    pageToken: str = Query(None),
):
    _li_auth(request)
    campaigns = [_li_campaign(ac) for ac in _LI_ADS]
    page, next_token = token_paginate(campaigns, pageToken, pageSize)
    return {"elements": page, "metadata": {"nextPageToken": next_token, "total": len(campaigns)}}


@router.get("/adAnalytics")
async def ad_analytics(
    request: Request,
    q: str = Query("analytics"),
    timeGranularity: str = Query("DAILY"),
    pivot: str = Query("CAMPAIGN"),
    start: int = Query(0),
    count: int = Query(30),
):
    _li_auth(request)

    elements = [
        {
            "dateRange": {"start": {"day": 1, "month": 6, "year": 2026}, "end": {"day": 2, "month": 6, "year": 2026}},
            "pivotValues": [f"urn:li:sponsoredCampaign:{_LI_ADS[0].id.replace('ad', '6123450')}" if _LI_ADS else "urn:li:sponsoredCampaign:0"],
            "impressions": 12500, "clicks": 185,
            "costInLocalCurrency": "2312.50", "costInUsd": "2312.50",
            "likes": 42, "comments": 8, "shares": 15, "follows": 5,
            "leadGenerationMailContactInfoShares": 0, "leadGenerationMailInterestedClicks": 0,
            "videoViews": 0, "videoCompletions": 0,
            "externalWebsiteConversions": 3, "oneClickLeads": 12,
        },
        {
            "dateRange": {"start": {"day": 2, "month": 6, "year": 2026}, "end": {"day": 3, "month": 6, "year": 2026}},
            "pivotValues": [f"urn:li:sponsoredCampaign:{_LI_ADS[0].id.replace('ad', '6123450')}" if _LI_ADS else "urn:li:sponsoredCampaign:0"],
            "impressions": 11800, "clicks": 172,
            "costInLocalCurrency": "2150.00", "costInUsd": "2150.00",
            "likes": 38, "comments": 5, "shares": 12, "follows": 3,
            "leadGenerationMailContactInfoShares": 0, "leadGenerationMailInterestedClicks": 0,
            "videoViews": 0, "videoCompletions": 0,
            "externalWebsiteConversions": 2, "oneClickLeads": 9,
        },
    ]

    return {
        "elements": elements,
        "paging": {"start": start, "count": count, "total": len(elements)},
    }
