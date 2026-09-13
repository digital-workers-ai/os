"""
LinkedIn Marketing API mock provider.
Contract: seeds/docs/13-linkedin-ads.md

Bearer auth + required Linkedin-Version header.
Cursor pagination (pageSize/pageToken) on adAccounts and adCampaigns.
"""

import re
from datetime import date, datetime, timezone

from fastapi import APIRouter, Request, Query
from seeds.helpers import (
    day_factor,
    day_ms,
    days_between,
    item_factor,
    offset_paginate,
    post_days,
    require_bearer,
    require_header,
    token_paginate,
    window_days,
)
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


ORGANIZATION = "urn:li:organization:1"

_COMMENTARY = [
    "Three lessons from a year of shipping weekly.",
    "We are hiring: come build with us.",
    "How our customers cut onboarding time in half.",
    "A look inside our engineering culture.",
    "Announcing our summer product update.",
]
_CONTENT_TYPES = ["ARTICLE", "IMAGE", "VIDEO"]


def _post(day):
    ordinal = day.toordinal() // 3
    stamp = day.strftime("%Y%m%d")
    return {
        "id": f"urn:li:share:{stamp}",
        "author": ORGANIZATION,
        "commentary": _COMMENTARY[ordinal % len(_COMMENTARY)],
        "contentType": _CONTENT_TYPES[ordinal % len(_CONTENT_TYPES)],
        "visibility": "PUBLIC",
        "lifecycleState": "PUBLISHED",
        "publishedAt": day_ms(day) + 14 * 3600 * 1000,
        "createdAt": day_ms(day) + 14 * 3600 * 1000,
        "lastModifiedAt": day_ms(day) + 14 * 3600 * 1000,
    }


def _share_statistics(urn):
    factor = item_factor(urn)
    return {
        "organizationalEntity": ORGANIZATION,
        "share": urn,
        "totalShareStatistics": {
            "uniqueImpressionsCount": round(1900 * factor),
            "impressionCount": round(2600 * factor),
            "clickCount": round(95 * factor),
            "likeCount": round(70 * factor),
            "commentCount": round(9 * factor),
            "shareCount": round(14 * factor),
            "engagement": round(0.06 * factor, 4),
        },
    }


def _interval_days(time_intervals):
    match = re.search(r"start:(\d+),end:(\d+)", time_intervals or "")
    if not match:
        return window_days()
    start = datetime.fromtimestamp(int(match.group(1)) / 1000, timezone.utc).date()
    end = datetime.fromtimestamp((int(match.group(2)) - 1) / 1000, timezone.utc).date()
    return days_between(start, end)


def _time_range(day):
    return {"start": day_ms(day), "end": day_ms(day) + 86_400_000}


def _shares_of(shares):
    inner = shares[5:-1] if shares and shares.startswith("List(") and shares.endswith(")") else (shares or "")
    return [urn for urn in inner.split(",") if urn]


@router.get("/posts")
async def list_posts(
    request: Request,
    author: str = Query(ORGANIZATION),
    q: str = Query("author"),
    start: int = Query(0, ge=0),
    count: int = Query(10, ge=1, le=100),
):
    _li_auth(request)
    posts = [_post(day) for day in post_days()]
    page, total = offset_paginate(posts, start, count)
    return {"elements": page, "paging": {"start": start, "count": count, "total": total, "links": []}}


@router.get("/organizationalEntityShareStatistics")
async def share_statistics(
    request: Request,
    q: str = Query("organizationalEntity"),
    organizationalEntity: str = Query(ORGANIZATION),
    shares: str = Query(None),
):
    _li_auth(request)
    urns = _shares_of(shares) or [post["id"] for post in (_post(day) for day in post_days())]
    elements = [_share_statistics(urn) for urn in urns]
    return {"elements": elements, "paging": {"start": 0, "count": len(elements), "total": len(elements), "links": []}}


@router.get("/organizationalEntityFollowerStatistics")
async def follower_statistics(
    request: Request,
    q: str = Query("organizationalEntity"),
    organizationalEntity: str = Query(ORGANIZATION),
    timeIntervals: str = Query(None),
):
    _li_auth(request)
    elements = [
        {
            "organizationalEntity": organizationalEntity,
            "timeRange": _time_range(day),
            "followerGains": {
                "organicFollowerGain": round(9 * day_factor(day)),
                "paidFollowerGain": round(3 * day_factor(day)),
            },
        }
        for day in _interval_days(timeIntervals)
    ]
    return {"elements": elements, "paging": {"start": 0, "count": len(elements), "total": len(elements), "links": []}}


@router.get("/organizationPageStatistics")
async def page_statistics(
    request: Request,
    q: str = Query("organization"),
    organization: str = Query(ORGANIZATION),
    timeIntervals: str = Query(None),
):
    _li_auth(request)
    elements = [
        {
            "organization": organization,
            "timeRange": _time_range(day),
            "totalPageStatistics": {
                "views": {
                    "allPageViews": {"pageViews": round(140 * day_factor(day))},
                    "overviewPageViews": {"pageViews": round(90 * day_factor(day))},
                    "careersPageViews": {"pageViews": round(30 * day_factor(day))},
                },
                "clicks": {"careersPageClicks": {"careersPageBannerPromoClicks": 0, "careersPageEmployeesClicks": 0, "careersPageJobsClicks": 0, "careersPagePromoLinksClicks": 0}},
            },
        }
        for day in _interval_days(timeIntervals)
    ]
    return {"elements": elements, "paging": {"start": 0, "count": len(elements), "total": len(elements), "links": []}}
