from collections import Counter
from datetime import date

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from seeds.helpers import day_factor, item_factor, require_bearer
from seeds.world import COMPETITOR_POSTS_BY_COMPETITOR, COMPETITORS, COMPETITORS_BY_ID

router = APIRouter()

DATASET = "gd_lyy3tktm25m4avu764"
DISCOVER_BY = "company_url"

_COMPANIES = {k.linkedin_url.rstrip("/"): k for k in COMPETITORS}
_FOLLOWERS = {"k1": 18400, "k2": 9600, "k3": 12700}
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
    posted_on = date.fromisoformat(post.posted_at[:10])
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
        "num_shares": max(0, round(reactions * 0.04 * day_factor(posted_on))),
        "post_type": "document" if "swipe" in post.text.lower() else "post",
        "user_followers": _FOLLOWERS[competitor.id],
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
    companies = [_COMPANIES.get(url.rstrip("/")) for url in urls]
    unknown = [url for url, company in zip(urls, companies) if company is None]
    if unknown:
        return _error(400, f"No LinkedIn company page known for {unknown[0]}")
    snapshot_id = f"s_{len(_SNAPSHOTS) + 1:06d}_{'_'.join(k.id for k in companies)}"
    _SNAPSHOTS[snapshot_id] = [k.id for k in companies]
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
    ids = _SNAPSHOTS.get(snapshot_id)
    if ids is None:
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
    posts = []
    for competitor_id in ids:
        competitor = COMPETITORS_BY_ID[competitor_id]
        newest_first = sorted(
            COMPETITOR_POSTS_BY_COMPETITOR[competitor_id],
            key=lambda p: p.posted_at,
            reverse=True,
        )
        posts += [_post(competitor, post) for post in newest_first]
    return posts
