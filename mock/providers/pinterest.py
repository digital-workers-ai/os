"""
Pinterest Ads API v5 mock provider.
Contract: seeds/docs/14-pinterest-ads.md

Bearer auth. Bookmark-based cursor pagination.
"""

from fastapi import APIRouter, Request, Query
from seeds.helpers import require_bearer, bookmark_paginate
from seeds.world import AD_CAMPAIGNS

router = APIRouter()

_PIN_ADS = [ac for ac in AD_CAMPAIGNS if ac.platform == "pinterest"]

_AD_ACCOUNTS = [
    {
        "id": "549764905678",
        "name": "Acme Corp",
        "owner": {"username": "acmecorp"},
        "country": "US", "currency": "USD", "status": "ACTIVE",
        "created_time": 1710500000, "updated_time": 1720000000,
        "permissions": ["ADMIN", "ANALYST", "CAMPAIGN_MANAGER"],
    },
    {
        "id": "549764905679",
        "name": "Globex Marketing",
        "owner": {"username": "globex"},
        "country": "US", "currency": "USD", "status": "ACTIVE",
        "created_time": 1715000000, "updated_time": 1720500000,
        "permissions": ["ADMIN"],
    },
]


def _pin_campaign(ac):
    return {
        "id": f"6267355{ac.id[-3:]}",
        "ad_account_id": "549764905678",
        "name": ac.name,
        "status": "ACTIVE" if ac.status == "active" else "PAUSED",
        "lifetime_spend_cap": ac.spend_cents * 10,
        "daily_spend_cap": ac.daily_budget_cents * 10,
        "objective_type": ac.objective.upper(),
        "created_time": 1719792000,
        "updated_time": 1720500000,
        "type": "campaign",
        "start_time": 1719792000,
        "end_time": 1727654400,
        "summary_status": "RUNNING" if ac.status == "active" else "NOT_STARTED",
        "is_flexible_daily_budgets": False,
        "default_ad_group_budget_in_micro_currency": None,
        "is_campaign_budget_optimization": True,
    }


@router.get("/ad_accounts")
async def list_ad_accounts(
    request: Request,
    page_size: int = Query(25, ge=1, le=250),
    bookmark: str = Query(None),
    include_shared_accounts: bool = Query(True),
):
    require_bearer(request)
    page, next_bm = bookmark_paginate(_AD_ACCOUNTS, bookmark, page_size)
    return {"items": page, "bookmark": next_bm}


@router.get("/ad_accounts/{ad_account_id}/campaigns")
async def list_campaigns(
    request: Request,
    ad_account_id: str,
    page_size: int = Query(25, ge=1, le=250),
    bookmark: str = Query(None),
    entity_statuses: str = Query(None),
    order: str = Query(None),
):
    require_bearer(request)
    campaigns = [_pin_campaign(ac) for ac in _PIN_ADS]
    page, next_bm = bookmark_paginate(campaigns, bookmark, page_size)
    return {"items": page, "bookmark": next_bm}


@router.get("/ad_accounts/{ad_account_id}/ad_groups")
async def list_ad_groups(
    request: Request,
    ad_account_id: str,
    page_size: int = Query(25, ge=1, le=250),
    bookmark: str = Query(None),
    campaign_ids: str = Query(None),
    entity_statuses: str = Query(None),
):
    require_bearer(request)
    ad_groups = [
        {
            "id": "2680060704746",
            "ad_account_id": ad_account_id,
            "campaign_id": f"6267355{_PIN_ADS[0].id[-3:]}" if _PIN_ADS else "626735500",
            "name": "Women 25-44 Interest",
            "status": "ACTIVE",
            "budget_in_micro_currency": 2000000,
            "budget_type": "DAILY",
            "bid_in_micro_currency": 150000,
            "bid_strategy_type": "AUTOMATIC_BID",
            "start_time": 1719792000, "end_time": 1727654400,
            "targeting_spec": {"GENDER": ["female"], "AGE_BUCKET": ["25-34", "35-44"], "INTEREST": ["fashion", "home_decor"], "LOCALE": ["en-US"]},
            "placement_group": "ALL",
            "pacing_delivery_type": "STANDARD",
            "optimization_goal_metadata": {"conversion_tag_v3_goal_metadata": None, "frequency_goal_metadata": None},
            "summary_status": "RUNNING",
            "created_time": 1719792000, "updated_time": 1720500000,
            "type": "adgroup",
        },
    ]
    return {"items": ad_groups, "bookmark": None}


@router.get("/ad_accounts/{ad_account_id}/ads")
async def list_ads(
    request: Request,
    ad_account_id: str,
    page_size: int = Query(25, ge=1, le=250),
    bookmark: str = Query(None),
    campaign_ids: str = Query(None),
    ad_group_ids: str = Query(None),
):
    require_bearer(request)
    ads = [
        {
            "id": "687201361234", "ad_account_id": ad_account_id,
            "ad_group_id": "2680060704746",
            "campaign_id": f"6267355{_PIN_ADS[0].id[-3:]}" if _PIN_ADS else "626735500",
            "name": "Summer Dress - Lifestyle Shot", "status": "ACTIVE",
            "creative_type": "REGULAR", "pin_id": "1055231234567",
            "review_status": "APPROVED", "rejection_labels": [],
            "summary_status": "RUNNING",
            "click_tracking_url": "https://acme.io/summer?ref=pinterest",
            "tracking_urls": {"impression": [], "click": []},
            "view_tracking_url": None,
            "created_time": 1719800000, "updated_time": 1720500000, "type": "ad",
        },
    ]
    return {"items": ads, "bookmark": None}


@router.get("/ad_accounts/{ad_account_id}/analytics")
async def account_analytics(
    request: Request,
    ad_account_id: str,
    start_date: str = Query(...),
    end_date: str = Query(...),
    columns: str = Query("IMPRESSION,CLICKTHROUGH,SPEND_IN_MICRO_DOLLAR"),
    granularity: str = Query("DAY"),
    click_window_days: int = Query(30),
):
    require_bearer(request)
    return [
        {"DATE": "2026-06-01", "IMPRESSION": 45000, "CLICKTHROUGH": 620, "SPEND_IN_MICRO_DOLLAR": 125000000, "CTR": 0.01378},
        {"DATE": "2026-06-02", "IMPRESSION": 42000, "CLICKTHROUGH": 580, "SPEND_IN_MICRO_DOLLAR": 118000000, "CTR": 0.01381},
    ]
