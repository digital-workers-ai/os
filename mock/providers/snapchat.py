"""
Snapchat Marketing API v1 mock provider.
Contract: seeds/docs/15-snapchat-ads.md

Bearer auth. Cursor pagination via paging.next_link.
All monetary values in micro-currency.
"""

from fastapi import APIRouter, Request, Query
from seeds.helpers import require_bearer

router = APIRouter()


@router.get("/v1/me/organizations")
async def list_organizations(request: Request):
    require_bearer(request)
    return {
        "request_status": "SUCCESS",
        "request_id": "63a1b2c3d4e5f6",
        "organizations": [
            {
                "sub_request_status": "SUCCESS",
                "organization": {
                    "id": "org_acme_001", "name": "Acme Corp Marketing",
                    "country": "US", "currency": "USD", "type": "ENTERPRISE", "state": "ACTIVE",
                    "roles": ["admin"], "my_display_name": "Jane Smith",
                    "my_invited_email": "jane@acme.io", "my_member_id": "mem_jane_001",
                    "created_at": "2025-01-10T08:00:00.000Z", "updated_at": "2026-06-15T10:30:00.000Z",
                },
            },
        ],
    }


@router.get("/v1/organizations/{organization_id}/adaccounts")
async def list_ad_accounts(
    request: Request,
    organization_id: str,
    limit: int = Query(1000, ge=50, le=1000),
    cursor: str = Query(None),
):
    require_bearer(request)
    return {
        "request_status": "SUCCESS",
        "request_id": "74b2c3d4e5f6a7",
        "adaccounts": [
            {
                "sub_request_status": "SUCCESS",
                "adaccount": {
                    "id": "adacct_acme_001", "name": "Acme Corp - US",
                    "type": "PARTNER", "status": "ACTIVE",
                    "organization_id": organization_id,
                    "currency": "USD", "timezone": "America/New_York",
                    "advertiser": "Acme Corp", "billing_type": "IO",
                    "lifetime_spend_cap_micro": 500000000000,
                    "advertiser_organization_id": organization_id,
                    "regulations": {"restricted_delivery_signals": False},
                    "created_at": "2025-02-01T10:00:00.000Z", "updated_at": "2026-07-01T12:00:00.000Z",
                },
            },
        ],
        "paging": {},
    }


@router.get("/v1/adaccounts/{ad_account_id}/campaigns")
async def list_campaigns(
    request: Request,
    ad_account_id: str,
    limit: int = Query(50),
    cursor: str = Query(None),
):
    require_bearer(request)
    return {
        "request_status": "SUCCESS",
        "request_id": "85c3d4e5f6a7b8",
        "campaigns": [
            {
                "sub_request_status": "SUCCESS",
                "campaign": {
                    "id": "camp_acme_brand_001", "name": "Acme Brand Awareness Q3",
                    "ad_account_id": ad_account_id, "status": "ACTIVE",
                    "objective": "BRAND_AWARENESS",
                    "start_time": "2026-07-01T00:00:00.000Z", "end_time": "2026-09-30T23:59:59.000Z",
                    "daily_budget_micro": 5000000000, "lifetime_spend_cap_micro": 450000000000,
                    "measurement_spec": {"ios_14_campaign_tracking_enabled": True},
                    "created_at": "2026-01-15T08:00:00.000Z", "updated_at": "2026-07-10T09:00:00.000Z",
                },
            },
            {
                "sub_request_status": "SUCCESS",
                "campaign": {
                    "id": "camp_acme_conv_001", "name": "Acme Product Launch - Conversions",
                    "ad_account_id": ad_account_id, "status": "ACTIVE",
                    "objective": "WEB_CONVERSIONS",
                    "start_time": "2026-03-01T00:00:00.000Z", "end_time": None,
                    "daily_budget_micro": 2500000000, "lifetime_spend_cap_micro": None,
                    "measurement_spec": {"ios_14_campaign_tracking_enabled": True},
                    "created_at": "2026-03-01T10:00:00.000Z", "updated_at": "2026-07-08T14:30:00.000Z",
                },
            },
        ],
        "paging": {},
    }


@router.get("/v1/adaccounts/{ad_account_id}/adsquads")
async def list_ad_squads(request: Request, ad_account_id: str, limit: int = Query(50), cursor: str = Query(None)):
    require_bearer(request)
    return {
        "request_status": "SUCCESS",
        "request_id": "96d4e5f6a7b8c9",
        "adsquads": [
            {
                "sub_request_status": "SUCCESS",
                "adsquad": {
                    "id": "adsq_acme_001", "name": "Acme 18-35 Interest Targeting",
                    "campaign_id": "camp_acme_brand_001", "status": "ACTIVE",
                    "type": "SNAP_ADS",
                    "placement_v2": {"config": "AUTOMATIC"},
                    "billing_event": "IMPRESSION", "auto_bid": True, "bid_strategy": "AUTO_BID",
                    "daily_budget_micro": 2500000000,
                    "start_time": "2026-07-01T00:00:00.000Z", "end_time": "2026-09-30T23:59:59.000Z",
                    "optimization_goal": "IMPRESSIONS",
                    "reach_and_frequency_status": "UNCAPPED",
                    "targeting": {
                        "geos": [{"country_code": "us"}],
                        "demographics": [{"age_groups": ["18-20", "21-24", "25-34"]}],
                        "interests": [{"category_id": "SLC_123", "name": "Technology"}],
                    },
                    "created_at": "2026-01-15T08:30:00.000Z", "updated_at": "2026-07-10T09:00:00.000Z",
                },
            },
        ],
        "paging": {},
    }


@router.get("/v1/adaccounts/{ad_account_id}/ads")
async def list_ads(request: Request, ad_account_id: str, limit: int = Query(50), cursor: str = Query(None)):
    require_bearer(request)
    return {
        "request_status": "SUCCESS",
        "request_id": "a7e5f6a7b8c9d0",
        "ads": [
            {
                "sub_request_status": "SUCCESS",
                "ad": {
                    "id": "ad_acme_001", "name": "Acme Hero Video - Summer 2026",
                    "ad_squad_id": "adsq_acme_001", "creative_id": "cre_acme_001",
                    "status": "ACTIVE", "type": "SNAP_AD",
                    "review_status": "APPROVED", "review_status_reasons": [],
                    "paying_advertiser_name": "Acme Corp",
                    "created_at": "2026-01-16T11:00:00.000Z", "updated_at": "2026-07-10T09:15:00.000Z",
                },
            },
            {
                "sub_request_status": "SUCCESS",
                "ad": {
                    "id": "ad_acme_002", "name": "Acme Product Demo - Carousel",
                    "ad_squad_id": "adsq_acme_001", "creative_id": "cre_acme_002",
                    "status": "ACTIVE", "type": "SNAP_AD",
                    "review_status": "APPROVED", "review_status_reasons": [],
                    "paying_advertiser_name": "Acme Corp",
                    "created_at": "2026-03-02T09:00:00.000Z", "updated_at": "2026-07-08T16:00:00.000Z",
                },
            },
        ],
        "paging": {},
    }


@router.get("/v1/adaccounts/{ad_account_id}/stats")
async def account_stats(
    request: Request,
    ad_account_id: str,
    granularity: str = Query("TOTAL"),
    start_time: str = Query(...),
    end_time: str = Query(...),
    fields: str = Query(None),
    breakdown: str = Query(None),
):
    require_bearer(request)
    return {
        "request_status": "SUCCESS",
        "request_id": "b8f6a7b8c9d0e1",
        "timeseries_stats": [
            {
                "sub_request_status": "SUCCESS",
                "timeseries_stat": {
                    "id": ad_account_id, "type": "AD_ACCOUNT",
                    "granularity": granularity,
                    "start_time": start_time, "end_time": end_time,
                    "finalized_data_end_time": "2026-07-06T00:00:00.000Z",
                    "timeseries": [
                        {
                            "start_time": "2026-07-01T00:00:00.000Z",
                            "end_time": "2026-07-02T00:00:00.000Z",
                            "stats": {
                                "impressions": 145200, "swipes": 3800, "spend": 4250000000,
                                "video_views": 98000, "video_views_time_based": 72000,
                                "video_views_15s": 45000, "screen_time_millis": 892000000,
                                "quartile_1": 120000, "quartile_2": 95000,
                                "quartile_3": 72000, "view_completion": 48000,
                                "frequency": 2.3, "uniques": 63130,
                            },
                        },
                        {
                            "start_time": "2026-07-02T00:00:00.000Z",
                            "end_time": "2026-07-03T00:00:00.000Z",
                            "stats": {
                                "impressions": 152800, "swipes": 4100, "spend": 4500000000,
                                "video_views": 103000, "video_views_time_based": 76000,
                                "video_views_15s": 48000, "screen_time_millis": 945000000,
                                "quartile_1": 126000, "quartile_2": 100000,
                                "quartile_3": 76000, "view_completion": 51000,
                                "frequency": 2.4, "uniques": 63667,
                            },
                        },
                    ],
                },
            },
        ],
    }
