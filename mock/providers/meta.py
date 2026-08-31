"""
Meta Ads + Facebook Organic + Instagram Organic mock provider.
Contracts: seeds/docs/04-meta-ads.md, 05-facebook-organic.md, 06-instagram-organic.md

All three share the Graph API and use query-param auth (?access_token=...).
Route conflict: /{id}/insights matches ads, FB pages, and IG accounts.
Resolved by dispatching on ID prefix (act_, page_, ig_).
"""

from fastapi import APIRouter, Request, Query
from seeds.helpers import require_query_token, cursor_paginate
from seeds.world import AD_CAMPAIGNS

router = APIRouter()

_META_ADS = [ac for ac in AD_CAMPAIGNS if ac.platform == "meta"]


def _ad_insight(ac, day="2026-07-01"):
    return {
        "account_id": f"act_{ac.company_id[1:].zfill(6)}",
        "campaign_id": ac.id,
        "campaign_name": ac.name,
        "impressions": str(ac.impressions),
        "clicks": str(ac.clicks),
        "spend": f"{ac.spend_cents / 100:.2f}",
        "conversions": str(ac.conversions),
        "ctr": f"{ac.clicks / ac.impressions:.6f}" if ac.impressions else "0",
        "cpc": f"{ac.spend_cents / ac.clicks / 100:.2f}" if ac.clicks else "0",
        "cpm": f"{ac.spend_cents / ac.impressions * 1000 / 100:.2f}" if ac.impressions else "0",
        "actions": [
            {"action_type": "link_click", "value": str(ac.clicks)},
            {"action_type": "landing_page_view", "value": str(max(1, ac.clicks // 2))},
            {"action_type": "offsite_conversion", "value": str(ac.conversions)},
        ],
        "objective": ac.objective,
        "date_start": day,
        "date_stop": day,
    }


def _campaign_obj(ac):
    return {
        "id": ac.id,
        "name": ac.name,
        "status": ac.status.upper(),
        "objective": ac.objective,
        "daily_budget": str(ac.daily_budget_cents),
        "lifetime_budget": "0",
        "budget_remaining": str(max(0, ac.daily_budget_cents * 30 - ac.spend_cents)),
        "start_time": f"{ac.start_date}T00:00:00-0700",
        "stop_time": f"{ac.end_date}T23:59:59-0700" if ac.end_date else None,
        "created_time": f"{ac.start_date}T00:00:00+0000",
        "updated_time": "2026-07-15T00:00:00+0000",
        "account_id": f"act_{ac.company_id[1:].zfill(6)}",
    }


# --- Unified insights handler (dispatches by node ID prefix) ---

@router.get("/v25.0/{node_id}/insights")
async def insights(
    request: Request,
    node_id: str,
    fields: str = Query("impressions,clicks,spend"),
    level: str = Query("campaign"),
    metric: str = Query("reach"),
    period: str = Query("day"),
    metric_type: str = Query(None),
    breakdown: str = Query(None),
    time_range: str = Query(None),
    time_increment: str = Query(None),
    since: int = Query(None),
    until: int = Query(None),
    limit: int = Query(25, ge=1, le=200),
    after: str = Query(None),
):
    require_query_token(request)

    if node_id.startswith("act_"):
        return _handle_ad_insights(node_id, limit, after)
    elif node_id.startswith("page_") and node_id.count("_") > 1:
        return _handle_post_insights(node_id, metric)
    elif node_id.startswith("page_"):
        return _handle_page_insights(node_id, metric, period)
    elif node_id.startswith("ig_"):
        return _handle_ig_insights(node_id, metric, period, metric_type, breakdown)
    elif node_id.startswith("media_"):
        return _handle_media_insights(node_id, metric)

    return {"data": []}


def _handle_ad_insights(account_id, limit, after):
    acct_num = account_id.replace("act_", "")
    matching = [ac for ac in _META_ADS if ac.company_id[1:].zfill(6) == acct_num]
    insights = [_ad_insight(ac) for ac in matching]
    page, next_cursor = cursor_paginate(insights, after, limit, id_field="campaign_id")
    result = {"data": page}
    if next_cursor:
        result["paging"] = {
            "cursors": {"before": "MAZDZD", "after": next_cursor},
            "next": f"https://graph.facebook.com/v25.0/{account_id}/insights?after={next_cursor}",
        }
    return result


def _handle_page_insights(page_id, metric, period):
    return {
        "data": [
            {
                "name": metric,
                "period": period,
                "values": [
                    {"value": 1250, "end_time": "2026-07-01T07:00:00+0000"},
                    {"value": 1380, "end_time": "2026-07-02T07:00:00+0000"},
                    {"value": 1100, "end_time": "2026-07-03T07:00:00+0000"},
                ],
                "title": metric.replace("_", " ").title(),
                "description": f"Daily: The number of {metric.replace('_', ' ')} for your Page.",
                "id": f"{page_id}/insights/{metric}/{period}",
            }
        ],
        "paging": {
            "previous": f"https://graph.facebook.com/v25.0/{page_id}/insights?since=1719705600&until=1719792000",
            "next": f"https://graph.facebook.com/v25.0/{page_id}/insights?since=1720051200&until=1720137600",
        },
    }


def _handle_post_insights(post_id, metric):
    _post_metrics = {
        "post_impressions": 8542, "post_engaged_users": 423, "post_clicks": 312,
        "post_reactions_by_type_total": 289, "post_activity": 735,
    }
    requested = [m.strip() for m in metric.split(",")] if metric else list(_post_metrics.keys())
    data = [
        {"name": m, "period": "lifetime", "values": [{"value": _post_metrics.get(m, 0)}],
         "title": m.replace("_", " ").title(), "id": f"{post_id}/insights/{m}/lifetime"}
        for m in requested if m in _post_metrics
    ]
    return {"data": data}


def _handle_media_insights(media_id, fields):
    _metrics = {
        "views": 8542, "reach": 6230, "total_interactions": 423, "saved": 87,
        "likes": 312, "comments": 28, "shares": 45, "reposts": 12,
        "ig_reels_avg_watch_time": 18.5, "ig_reels_video_view_total_time": 42350,
        "follows": 15, "profile_visits": 67, "replies": 8, "navigation": 23,
    }
    requested = [m.strip() for m in fields.split(",")] if fields else ["views", "reach", "total_interactions"]
    data = [
        {"name": m, "period": "lifetime", "values": [{"value": _metrics.get(m, 0)}], "id": f"{media_id}/insights/{m}/lifetime"}
        for m in requested if m in _metrics
    ]
    return {"data": data}


def _handle_ig_insights(ig_id, metric, period, metric_type, breakdown):
    if metric == "follower_demographics" and metric_type == "total_value" and breakdown:
        dim_key = breakdown
        _breakdowns = {
            "country": [("US", 5240), ("GB", 1820), ("CA", 1350), ("AU", 980), ("DE", 720)],
            "city": [("Los Angeles, California", 1200), ("London, England", 900), ("Toronto, Ontario", 650)],
            "age": [("18-24", 2150), ("25-34", 5420), ("35-44", 3890), ("45-54", 2100), ("55-64", 980), ("65+", 450)],
            "gender": [("M", 7200), ("F", 6800), ("U", 990)],
        }
        results = [{"dimension_values": ["lifetime", v], "value": n} for v, n in _breakdowns.get(dim_key, [])]
        return {
            "data": [{
                "name": "follower_demographics", "period": "lifetime", "title": "Follower demographics",
                "total_value": {"breakdowns": [{"dimension_keys": ["timeframe", dim_key], "results": results}]},
                "id": f"{ig_id}/insights/follower_demographics/lifetime",
            }]
        }
    if metric_type == "total_value":
        metrics_requested = [m.strip() for m in metric.split(",")]
        _tv = {"accounts_engaged": 892, "total_interactions": 1456, "likes": 823, "comments": 156, "shares": 234, "saves": 189, "replies": 52}
        data = [{"name": m, "period": period, "total_value": {"value": _tv.get(m, 100)}, "title": m.replace("_", " ").title(), "id": f"{ig_id}/insights/{m}/{period}"} for m in metrics_requested]
        return {"data": data}
    return {
        "data": [
            {
                "name": metric,
                "period": period,
                "values": [
                    {"value": 3421, "end_time": "2026-07-01T07:00:00+0000"},
                    {"value": 4102, "end_time": "2026-07-02T07:00:00+0000"},
                    {"value": 2891, "end_time": "2026-07-03T07:00:00+0000"},
                ],
                "title": metric.replace("_", " ").title(),
                "id": f"{ig_id}/insights/{metric}/{period}",
            }
        ],
        "paging": {
            "previous": f"https://graph.facebook.com/v25.0/{ig_id}/insights?since=1719705600&until=1719792000",
            "next": f"https://graph.facebook.com/v25.0/{ig_id}/insights?since=1720051200&until=1720137600",
        },
    }


# --- Campaign List ---

@router.get("/v25.0/{account_id}/campaigns")
async def list_campaigns(
    request: Request,
    account_id: str,
    fields: str = Query("name,status,objective"),
    limit: int = Query(25, ge=1, le=500),
    after: str = Query(None),
):
    require_query_token(request)
    acct_num = account_id.replace("act_", "")
    matching = [ac for ac in _META_ADS if ac.company_id[1:].zfill(6) == acct_num]
    campaigns = [_campaign_obj(ac) for ac in matching]
    page, next_cursor = cursor_paginate(campaigns, after, limit)
    result = {"data": page}
    if next_cursor:
        result["paging"] = {
            "cursors": {"before": "MAZDZD", "after": next_cursor},
            "next": f"https://graph.facebook.com/v25.0/{account_id}/campaigns?after={next_cursor}",
        }
    return result


# --- Facebook Page Posts ---

@router.get("/v25.0/{page_id}/posts")
async def page_posts(
    request: Request,
    page_id: str,
    fields: str = Query("message,created_time"),
    limit: int = Query(25, ge=1, le=100),
    after: str = Query(None),
):
    require_query_token(request)
    posts = [
        {"id": f"{page_id}_001", "message": "Exciting news! We just launched our new feature.", "created_time": "2026-07-10T14:00:00+0000", "permalink_url": f"https://www.facebook.com/mybusiness/posts/{page_id}_001", "type": "link", "shares": {"count": 45}, "likes": {"data": [], "summary": {"total_count": 312, "can_like": True, "has_liked": False}}, "comments": {"data": [], "summary": {"total_count": 28, "can_comment": True}}},
        {"id": f"{page_id}_002", "message": "Join our upcoming webinar on AI in 2026.", "created_time": "2026-07-08T10:00:00+0000", "permalink_url": f"https://www.facebook.com/mybusiness/posts/{page_id}_002", "type": "photo", "shares": {"count": 12}, "likes": {"data": [], "summary": {"total_count": 189, "can_like": True, "has_liked": False}}, "comments": {"data": [], "summary": {"total_count": 15, "can_comment": True}}},
        {"id": f"{page_id}_003", "message": "Customer spotlight: How Globex grew 40% with us.", "created_time": "2026-07-05T12:00:00+0000", "permalink_url": f"https://www.facebook.com/mybusiness/posts/{page_id}_003", "type": "link", "shares": {"count": 23}, "likes": {"data": [], "summary": {"total_count": 245, "can_like": True, "has_liked": False}}, "comments": {"data": [], "summary": {"total_count": 19, "can_comment": True}}},
    ]
    page, next_cursor = cursor_paginate(posts, after, limit)
    result = {"data": page}
    if next_cursor:
        result["paging"] = {
            "cursors": {"before": "MAZDZD", "after": next_cursor},
            "next": f"https://graph.facebook.com/v25.0/{page_id}/posts?after={next_cursor}",
        }
    return result


@router.get("/v25.0/{post_id}/comments")
async def post_comments(
    request: Request,
    post_id: str,
    limit: int = Query(25, ge=1, le=100),
    after: str = Query(None),
):
    require_query_token(request)
    comments = [
        {"id": f"{post_id}_comment_001", "message": "Great update!", "created_time": "2026-07-10T15:00:00+0000", "from": {"name": "User One", "id": "user_001"}},
        {"id": f"{post_id}_comment_002", "message": "Looking forward to trying this.", "created_time": "2026-07-10T16:00:00+0000", "from": {"name": "User Two", "id": "user_002"}},
    ]
    return {"data": comments, "paging": {"cursors": {"before": "MAZDZD", "after": "MjQZD"}}}


@router.get("/v25.0/{post_id}/reactions")
async def post_reactions(
    request: Request,
    post_id: str,
    type: str = Query(None),
    limit: int = Query(25, ge=1, le=100),
    after: str = Query(None),
):
    require_query_token(request)
    reactions = [
        {"id": "user_001", "name": "User One", "type": "LIKE"},
        {"id": "user_002", "name": "User Two", "type": "LOVE"},
        {"id": "user_003", "name": "User Three", "type": "LIKE"},
    ]
    if type:
        reactions = [r for r in reactions if r["type"] == type]
    return {"data": reactions, "paging": {"cursors": {"before": "MAZDZD", "after": "MjQZD"}}, "summary": {"total_count": len(reactions)}}


# --- Instagram Media ---

@router.get("/v25.0/{ig_id}/media")
async def ig_media(
    request: Request,
    ig_id: str,
    fields: str = Query("id,caption,timestamp,media_type"),
    limit: int = Query(25, ge=1, le=100),
    after: str = Query(None),
):
    require_query_token(request)
    media = [
        {"id": "media_001", "caption": "New product launch!", "timestamp": "2026-07-05T14:30:00+0000", "media_type": "CAROUSEL_ALBUM", "media_product_type": "FEED", "permalink": "https://www.instagram.com/p/abc123/", "media_url": "https://scontent.xx.fbcdn.net/v/media_001.jpg", "thumbnail_url": "https://scontent.xx.fbcdn.net/v/media_001_thumb.jpg"},
        {"id": "media_002", "caption": "Behind the scenes", "timestamp": "2026-07-03T10:00:00+0000", "media_type": "IMAGE", "media_product_type": "FEED", "permalink": "https://www.instagram.com/p/def456/", "media_url": "https://scontent.xx.fbcdn.net/v/media_002.jpg"},
        {"id": "media_003", "caption": "Quick tip in 60 seconds", "timestamp": "2026-07-01T16:00:00+0000", "media_type": "VIDEO", "media_product_type": "REELS", "permalink": "https://www.instagram.com/reel/ghi789/", "thumbnail_url": "https://scontent.xx.fbcdn.net/v/media_003_thumb.jpg"},
    ]
    page, next_cursor = cursor_paginate(media, after, limit)
    result = {"data": page}
    if next_cursor:
        result["paging"] = {
            "cursors": {"before": "MAZDZD", "after": next_cursor},
            "next": f"https://graph.facebook.com/v25.0/{ig_id}/media?after={next_cursor}",
        }
    return result


# --- Page Token Exchange ---

@router.get("/v25.0/{ig_id}/tags")
async def ig_tagged_media(
    request: Request,
    ig_id: str,
    limit: int = Query(25, ge=1, le=100),
    after: str = Query(None),
):
    require_query_token(request)
    tagged = [
        {"id": "tagged_001", "caption": "Love using @mybusiness for our workflow!", "timestamp": "2026-07-04T12:00:00+0000", "media_type": "IMAGE", "permalink": "https://www.instagram.com/p/xyz789/"},
    ]
    result = {"data": tagged, "paging": {"cursors": {"before": "MAZDZD", "after": "MjQZD"}}}
    return result


@router.get("/v25.0/me/accounts")
async def me_accounts(request: Request):
    require_query_token(request)
    return {
        "data": [
            {"id": "page_001", "name": "Acme Corp", "access_token": "mock_page_token_001"},
        ]
    }


@router.get("/v25.0/{node_id}")
async def node_metadata(
    request: Request,
    node_id: str,
    fields: str = Query(""),
):
    require_query_token(request)
    if node_id.startswith("ig_"):
        result = {"id": node_id}
        if "content_publishing_limit" in fields:
            result["content_publishing_limit"] = {"quota_usage": 3, "config": {"quota_total": 25, "quota_duration": 86400}}
        else:
            result["followers_count"] = 15420
            result["media_count"] = 342
        return result
    if node_id.startswith("page_"):
        return {
            "id": node_id,
            "name": "Acme Corp",
            "followers_count": 12500,
            "fan_count": 12200,
            "rating_count": 48,
            "overall_star_rating": 4.6,
            "talking_about_count": 320,
            "website": "https://acme.example.com",
        }
    if node_id.startswith("act_"):
        return {"id": node_id, "timezone_name": "America/Los_Angeles"}
    return {"id": node_id}
