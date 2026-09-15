from datetime import date

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from seeds.helpers import day_factor, item_factor, require_bearer
from seeds.world import COMPETITOR_POSTS_BY_COMPETITOR, COMPETITORS_BY_DOMAIN

router = APIRouter()

_PLATFORM = "linkedin"


def _activity_id(post):
    return f"7241{post.id[2:].zfill(15)}"


def _post(post):
    activity_id = _activity_id(post)
    reactions = post.reactions
    posted_on = date.fromisoformat(post.posted_at[:10])
    return {
        "id": activity_id,
        "url": f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}/",
        "text": post.text,
        "posted_at": post.posted_at,
        "reactions": reactions,
        "comments": max(1, round(reactions * 0.11 * item_factor(post.id))),
        "reposts": max(0, round(reactions * 0.04 * day_factor(posted_on))),
        "platform": _PLATFORM,
    }


@router.get("/v1/posts")
async def posts(
    request: Request,
    domain: str = Query(...),
    limit: int = Query(None, ge=1, le=100),
):
    require_bearer(request)
    competitor = COMPETITORS_BY_DOMAIN.get(domain)
    if competitor is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "type": "record-not-found",
                    "message": f"Domain '{domain}' is not in this collector's input.",
                }
            },
        )
    newest_first = sorted(
        COMPETITOR_POSTS_BY_COMPETITOR[competitor.id],
        key=lambda p: p.posted_at,
        reverse=True,
    )
    rendered = [_post(post) for post in newest_first]
    return {"posts": rendered[:limit] if limit else rendered, "cursor": None}
