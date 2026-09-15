from fastapi import APIRouter, Query, Request
from seeds.helpers import day_factor, post_days, token_paginate

router = APIRouter()


class _TwAuthError(Exception):
    pass


def _tw_auth(request: Request):
    auth = request.headers.get("authorization", "")
    if not auth:
        raise _TwAuthError()


_TWEET_TEXTS = [
    "We just shipped a faster sync. Details in the thread.",
    "What our customers taught us this quarter.",
    "Live now: our webinar on AI in 2026.",
    "Hiring engineers who like hard problems.",
    "A small change that halved our support queue.",
]


def _tweet(day, fields):
    ordinal = day.toordinal() // 3
    factor = day_factor(day)
    stamp = day.strftime("%Y%m%d")
    tweet = {
        "id": f"tweet_{stamp}",
        "edit_history_tweet_ids": [f"tweet_{stamp}"],
        "text": _TWEET_TEXTS[ordinal % len(_TWEET_TEXTS)],
    }
    if "created_at" in fields:
        tweet["created_at"] = f"{day.isoformat()}T15:00:00.000Z"
    if "public_metrics" in fields:
        tweet["public_metrics"] = {
            "retweet_count": round(18 * factor),
            "reply_count": round(7 * factor),
            "like_count": round(120 * factor),
            "quote_count": round(3 * factor),
            "bookmark_count": round(11 * factor),
            "impression_count": round(4200 * factor),
        }
    return tweet


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
    fields = {f.strip() for f in (tweet_fields or "").split(",") if f.strip()}
    tweets = [
        _tweet(day, fields) for day in reversed(post_days(start_time, end_time))
    ]
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
