"""
X/Twitter Ads API v12 mock provider.
Contract: seeds/docs/16-twitter-ads.md

OAuth 1.0a auth (mock: just check Authorization header exists).
Cursor pagination via next_cursor.
Monetary values in micro-currency. Stats as arrays.
"""

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from seeds.helpers import day_factor, post_days, require_header, token_paginate

router = APIRouter()


def _tw_auth(request: Request):
    auth = request.headers.get("authorization", "")
    if not auth:
        raise _TwAuthError()


class _TwAuthError(Exception):
    pass


@router.get("/12/accounts")
async def list_accounts(
    request: Request,
    count: int = Query(200, ge=1, le=1000),
    cursor: str = Query(None),
    with_deleted: bool = Query(False),
):
    _tw_auth(request)
    data = [
        {
            "id": "twacct_acme_001", "name": "Acme Corp Ads",
            "business_name": "Acme Corp", "business_id": "twbiz_acme_001",
            "timezone": "US/Eastern", "country_code": "US", "currency": "USD",
            "timezone_switch_at": "2025-01-10T08:00:00Z",
            "salt": "abc123def456",
            "created_at": "2025-01-10T08:00:00Z", "updated_at": "2026-07-01T12:00:00Z",
            "approval_status": "ACCEPTED", "deleted": False,
            "industry_type": "TECHNOLOGY",
        },
        {
            "id": "twacct_globex_001", "name": "Globex Inc Advertising",
            "business_name": "Globex Inc", "business_id": "twbiz_globex_001",
            "timezone": "US/Pacific", "country_code": "US", "currency": "USD",
            "timezone_switch_at": "2025-03-15T09:00:00Z",
            "salt": "ghi789jkl012",
            "created_at": "2025-03-15T09:00:00Z", "updated_at": "2026-06-20T14:00:00Z",
            "approval_status": "ACCEPTED", "deleted": False,
            "industry_type": "RETAIL",
        },
    ]
    return {
        "data": data, "total_count": len(data), "next_cursor": None,
        "request": {"params": {"count": count, "cursor": cursor, "with_deleted": with_deleted}},
    }


@router.get("/12/accounts/{account_id}/campaigns")
async def list_campaigns(
    request: Request,
    account_id: str,
    count: int = Query(200, ge=1, le=1000),
    cursor: str = Query(None),
    with_deleted: bool = Query(False),
    with_draft: bool = Query(False),
):
    _tw_auth(request)
    data = [
        {
            "id": "twcamp_acme_brand_001", "name": "Acme Brand Awareness Summer 2026",
            "account_id": account_id, "funding_instrument_id": "twfi_acme_001",
            "entity_status": "ACTIVE", "servable": True,
            "start_time": "2026-07-01T00:00:00Z", "end_time": "2026-09-30T23:59:59Z",
            "daily_budget_amount_local_micro": 5000000000,
            "total_budget_amount_local_micro": 450000000000,
            "currency": "USD", "standard_delivery": True,
            "frequency_cap": 3, "duration_in_days": 7,
            "purchase_order_number": None,
            "created_at": "2026-06-25T10:00:00Z", "updated_at": "2026-07-10T09:00:00Z",
            "deleted": False,
        },
        {
            "id": "twcamp_acme_conv_001", "name": "Acme Product Launch Q3",
            "account_id": account_id, "funding_instrument_id": "twfi_acme_001",
            "entity_status": "ACTIVE", "servable": True,
            "start_time": "2026-07-15T00:00:00Z", "end_time": None,
            "daily_budget_amount_local_micro": 2500000000,
            "total_budget_amount_local_micro": None,
            "currency": "USD", "standard_delivery": True,
            "frequency_cap": None, "duration_in_days": None,
            "purchase_order_number": None,
            "created_at": "2026-07-10T14:00:00Z", "updated_at": "2026-07-10T14:00:00Z",
            "deleted": False,
        },
    ]
    return {
        "data": data, "total_count": len(data), "next_cursor": None,
        "request": {"params": {"account_id": account_id, "count": count, "cursor": cursor, "with_deleted": with_deleted, "with_draft": with_draft}},
    }


@router.get("/12/accounts/{account_id}/line_items")
async def list_line_items(
    request: Request,
    account_id: str,
    count: int = Query(200, ge=1, le=1000),
    cursor: str = Query(None),
    campaign_ids: str = Query(None),
    with_deleted: bool = Query(False),
):
    _tw_auth(request)
    data = [
        {
            "id": "twli_acme_001", "name": "Acme - 18-34 Tech Interest",
            "campaign_id": "twcamp_acme_brand_001", "account_id": account_id,
            "entity_status": "ACTIVE", "servable": True,
            "objective": "REACH", "placements": ["ALL_ON_TWITTER"],
            "product_type": "PROMOTED_TWEETS", "bid_strategy": "AUTO",
            "bid_amount_local_micro": None, "charge_by": "IMPRESSION",
            "target_cpa_local_micro": None,
            "daily_budget_amount_local_micro": None,
            "total_budget_amount_local_micro": None,
            "optimization": "DEFAULT", "advertiser_domain": "acme.io",
            "start_time": "2026-07-01T00:00:00Z", "end_time": "2026-09-30T23:59:59Z",
            "automatically_select_bid": True,
            "audience_expansion": None,
            "tracking_tags": [],
            "pay_by": "IMPRESSION",
            "creative_source": "MANUAL",
            "created_at": "2026-06-25T10:30:00Z", "updated_at": "2026-07-10T09:00:00Z",
            "deleted": False,
        },
    ]
    return {
        "data": data, "total_count": len(data), "next_cursor": None,
        "request": {"params": {"account_id": account_id, "count": count, "cursor": cursor, "campaign_ids": campaign_ids, "with_deleted": with_deleted}},
    }


@router.get("/12/stats/accounts/{account_id}")
async def account_stats(
    request: Request,
    account_id: str,
    entity: str = Query(...),
    entity_ids: str = Query(...),
    start_time: str = Query(...),
    end_time: str = Query(...),
    granularity: str = Query("DAY"),
    metric_groups: str = Query("ENGAGEMENT"),
    placement: str = Query("ALL_ON_TWITTER"),
):
    _tw_auth(request)
    ids = entity_ids.split(",")
    data = []
    for eid in ids:
        data.append({
            "id": eid.strip(),
            "id_data": [
                {
                    "segment": None,
                    "metrics": {
                        "impressions": [145200, 152800, 148600, 155100, 142000, 160300, 158900],
                        "engagements": [8200, 8900, 8500, 9100, 7800, 9400, 9200],
                        "clicks": [3800, 4100, 3900, 4200, 3600, 4500, 4300],
                        "likes": [2100, 2300, 2200, 2400, 2000, 2600, 2500],
                        "retweets": [450, 480, 460, 510, 420, 530, 500],
                        "replies": [120, 130, 125, 140, 110, 150, 140],
                        "follows": [35, 42, 38, 45, 30, 48, 44],
                        "url_clicks": [1800, 1950, 1850, 2000, 1700, 2100, 2050],
                        "billed_engagements": [145200, 152800, 148600, 155100, 142000, 160300, 158900],
                        "billed_charge_local_micro": [4250000000, 4500000000, 4350000000, 4600000000, 4100000000, 4750000000, 4680000000],
                    },
                },
            ],
        })

    return {
        "data": data,
        "data_type": "stats",
        "time_series_length": 7,
        "request": {
            "params": {
                "account_id": account_id, "entity": entity,
                "entity_ids": ids, "start_time": start_time, "end_time": end_time,
                "granularity": granularity, "metric_groups": metric_groups.split(","),
                "placement": placement,
            },
        },
    }


_TWEET_TEXTS = [
    "We just shipped a faster sync. Details in the thread.",
    "What our customers taught us this quarter.",
    "Live now: our webinar on AI in 2026.",
    "Hiring engineers who like hard problems.",
    "A small change that halved our support queue.",
]


def _tweet(day):
    ordinal = day.toordinal() // 3
    factor = day_factor(day)
    stamp = day.strftime("%Y%m%d")
    return {
        "id": f"tweet_{stamp}",
        "text": _TWEET_TEXTS[ordinal % len(_TWEET_TEXTS)],
        "created_at": f"{day.isoformat()}T15:00:00.000Z",
        "edit_history_tweet_ids": [f"tweet_{stamp}"],
        "public_metrics": {
            "retweet_count": round(18 * factor),
            "reply_count": round(7 * factor),
            "like_count": round(120 * factor),
            "quote_count": round(3 * factor),
            "bookmark_count": round(11 * factor),
            "impression_count": round(4200 * factor),
        },
    }


@router.get("/2/users/{user_id}/tweets")
async def user_tweets(
    request: Request,
    user_id: str,
    start_time: str = Query(None),
    end_time: str = Query(None),
    max_results: int = Query(10, ge=5, le=100),
    pagination_token: str = Query(None),
    tweet_fields: str = Query(None, alias="tweet.fields"),
):
    _tw_auth(request)
    tweets = [_tweet(day) for day in reversed(post_days(start_time, end_time))]
    page, next_token = token_paginate(tweets, pagination_token, max_results)
    meta = {"result_count": len(page)}
    if page:
        meta["newest_id"] = page[0]["id"]
        meta["oldest_id"] = page[-1]["id"]
    if next_token:
        meta["next_token"] = next_token
    body = {"meta": meta}
    if page:
        body["data"] = page
    return body
