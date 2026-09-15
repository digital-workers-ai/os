from collections import Counter

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from seeds.helpers import item_factor, require_bearer
from seeds.world import COMPETITOR_POSTS_BY_COMPETITOR, COMPETITORS

router = APIRouter()

DATASET = "gd_lyy3tktm25m4avu764"
DISCOVER_BY = "company_url"

_COMPANIES = {k.linkedin_url.rstrip("/"): k for k in COMPETITORS}
_FOLLOWERS = {"k1": 18400, "k2": 9600, "k3": 12700}
_COLLECTED_AT = "2026-09-15T05:50:00.000Z"
_SNAPSHOTS: dict = {}
_POLLS: Counter = Counter()


def _error(status, message):
    return JSONResponse(status_code=status, content={"error": message})


def _slug(company_url):
    return company_url.rstrip("/").rsplit("/", 1)[-1]


def _activity_id(post):
    return f"7241{post.id[2:].zfill(15)}"


def _post(competitor, post):
    activity_id = _activity_id(post)
    reactions = post.reactions
    slug = _slug(competitor.linkedin_url)
    return {
        "url": f"https://www.linkedin.com/posts/{slug}_activity-{activity_id}",
        "id": activity_id,
        "user_id": competitor.linkedin_url,
        "post_text": post.text,
        "date_posted": post.posted_at.replace("Z", ".000Z"),
        "hashtags": [f"#{competitor.name.lower()}", "#ugc"],
        "num_likes": reactions,
        "num_comments": max(1, round(reactions * 0.11 * item_factor(post.id))),
        "post_type": "document" if "swipe" in post.text.lower() else "post",
        "account_type": "Organization",
        "user_followers": _FOLLOWERS[competitor.id],
        "repost": {},
        "timestamp": _COLLECTED_AT,
    }


def _dead_page(company_url):
    return {
        "timestamp": _COLLECTED_AT,
        "input": {"url": company_url},
        "error": "Activities are not found",
        "error_code": "dead_page",
    }


async def _inputs(request):
    try:
        body = await request.json()
    except ValueError:
        return None
    if not isinstance(body, list) or not body:
        return None
    urls = [item.get("url") if isinstance(item, dict) else None for item in body]
    if not all(isinstance(url, str) and url for url in urls):
        return None
    return urls


@router.post("/datasets/v3/trigger")
async def trigger(
    request: Request,
    dataset_id: str = Query(...),
    kind: str = Query("discover_new", alias="type"),
    discover_by: str = Query(...),
    fmt: str = Query("json", alias="format"),
    include_errors: bool = Query(False),
):
    require_bearer(request)
    if dataset_id != DATASET:
        return _error(404, f"Dataset {dataset_id} not found")
    if kind != "discover_new" or discover_by != DISCOVER_BY:
        return _error(400, f"This dataset is discovered by {DISCOVER_BY} only")
    if fmt != "json":
        return _error(400, "Only format=json is served")
    urls = await _inputs(request)
    if urls is None:
        return _error(400, "Input must be a non-empty list of objects with a url")
    snapshot_id = f"s_{len(_SNAPSHOTS) + 1:06d}"
    _SNAPSHOTS[snapshot_id] = urls
    return {"snapshot_id": snapshot_id}


@router.get("/datasets/v3/progress/{snapshot_id}")
async def progress(request: Request, snapshot_id: str):
    require_bearer(request)
    if snapshot_id not in _SNAPSHOTS:
        return _error(404, f"Snapshot {snapshot_id} not found")
    _POLLS[snapshot_id] += 1
    status = "running" if _POLLS[snapshot_id] == 1 else "ready"
    return {"snapshot_id": snapshot_id, "dataset_id": DATASET, "status": status}


@router.get("/datasets/v3/snapshot/{snapshot_id}")
async def snapshot(
    request: Request, snapshot_id: str, fmt: str = Query("json", alias="format")
):
    require_bearer(request)
    urls = _SNAPSHOTS.get(snapshot_id)
    if urls is None:
        return _error(404, f"Snapshot {snapshot_id} not found")
    if fmt != "json":
        return _error(400, "Only format=json is served")
    if _POLLS[snapshot_id] < 2:
        return JSONResponse(
            status_code=202,
            content={
                "status": "running",
                "message": "Snapshot is not ready yet, check again in 10s",
            },
        )
    rows = []
    for url in urls:
        competitor = _COMPANIES.get(url.rstrip("/"))
        if competitor is None:
            rows.append(_dead_page(url))
            continue
        newest_first = sorted(
            COMPETITOR_POSTS_BY_COMPETITOR[competitor.id],
            key=lambda p: p.posted_at,
            reverse=True,
        )
        rows += [_post(competitor, post) for post in newest_first]
    return rows
