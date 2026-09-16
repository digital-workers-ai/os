import base64
import json
from urllib.parse import urlparse

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse

from seeds import world

router = APIRouter()

DATASET_ID = "gd_lyy3tktm25m4avu764"
COLLECTION_MS = 36592
_ASKED: set[str] = set()
_STAMP = f"{world.SPY_ANCHOR.isoformat()}T12:00:00.000Z"
_RECORD_KEYS = (
    "url",
    "id",
    "user_id",
    "use_url",
    "title",
    "headline",
    "post_text",
    "date_posted",
    "hashtags",
    "embedded_links",
    "images",
    "videos",
    "num_likes",
    "num_comments",
    "more_articles_by_user",
    "more_relevant_posts",
    "top_visible_comments",
    "user_followers",
    "user_posts",
    "user_articles",
    "post_type",
    "account_type",
    "post_text_html",
    "repost",
    "tagged_companies",
    "tagged_people",
    "user_title",
    "author_profile_pic",
    "num_connections",
    "video_duration",
    "external_link_data",
    "video_thumbnail",
    "document_cover_image",
    "document_page_count",
    "user_profile_pic",
    "user_name",
    "original_post_text",
    "timestamp",
    "input",
    "discovery_input",
)


def _text(message: str, status: int) -> Response:
    return Response(message, status_code=status, media_type="text/html")


def _denied(request: Request):
    auth = request.headers.get("authorization")
    if auth is None:
        return _text("Credentials are missing", 401)
    if not auth.startswith("Bearer ") or len(auth) == 7:
        return _text("Auth method is not supported", 401)
    return None


def _slug(url: str) -> str:
    return urlparse(url).path.strip("/").split("/")[-1]


def _slugs(snapshot_id: str):
    try:
        return base64.urlsafe_b64decode(snapshot_id).decode().split(",")
    except (ValueError, UnicodeDecodeError):
        return None


def _complete(post: dict) -> dict:
    logo = f"https://media.licdn.com/dms/image/v2/company-logo_100_100/0/{post['user_id']}_logo?e=2147483647&v=beta"
    filled = {
        "headline": post["post_text"].split("\n")[0],
        "more_articles_by_user": None,
        "more_relevant_posts": None,
        "top_visible_comments": [],
        "user_posts": 0,
        "user_articles": 0,
        "user_title": None,
        "author_profile_pic": logo,
        "num_connections": None,
        "video_duration": None,
        "external_link_data": None,
        "video_thumbnail": None,
        "document_cover_image": None,
        "document_page_count": None,
        "user_profile_pic": logo,
        "user_name": post["title"],
        "original_post_text": post["post_text"],
        "timestamp": _STAMP,
        "input": {
            "url": f"https://www.linkedin.com/feed/update/urn:li:activity:{post['id']}"
        },
        "discovery_input": {"url": post["use_url"]},
        **post,
    }
    return {key: filled[key] for key in _RECORD_KEYS}


def _records(slugs: list[str]) -> list[dict]:
    records = []
    for slug in slugs:
        posts = world.spy_posts(slug)
        if not posts:
            records.append(
                {
                    "timestamp": _STAMP,
                    "input": {"url": f"https://www.linkedin.com/company/{slug}"},
                    "error": "4XX page - dead page.",
                    "error_code": "dead_page",
                }
            )
        records.extend(_complete(post) for post in posts)
    return records


@router.post("/datasets/v3/trigger")
async def trigger(
    request: Request, dataset_id: str = Query(None), discover_by: str = Query(None)
):
    denied = _denied(request)
    if denied:
        return denied
    if dataset_id != DATASET_ID:
        return _text("dataset does not exist", 404)
    if discover_by != "company_url":
        return _text(
            "Incorrect discovery collector id "
            "Available types: url, profile_url, company_url",
            400,
        )
    try:
        inputs = json.loads(await request.body())
    except ValueError:
        return JSONResponse(
            {
                "error": "Parser cannot parse input: expected a value",
                "code": "parse_error",
            },
            status_code=400,
        )
    if not isinstance(inputs, list):
        inputs = [inputs]
    if not inputs:
        return _text("No data to trigger", 400)
    for index, item in enumerate(inputs, start=1):
        if not isinstance(item, dict) or "url" not in item:
            return JSONResponse(
                {
                    "error": "Invalid input provided",
                    "code": "validation_error",
                    "type": "validation",
                    "line": json.dumps(item, separators=(",", ":")),
                    "index": index,
                    "errors": [["url", "Required field"]],
                },
                status_code=400,
            )
    slugs = ",".join(_slug(item["url"]) for item in inputs)
    return {"snapshot_id": base64.urlsafe_b64encode(slugs.encode()).decode()}


@router.get("/datasets/v3/progress/{snapshot_id}")
async def progress(request: Request, snapshot_id: str):
    denied = _denied(request)
    if denied:
        return denied
    slugs = _slugs(snapshot_id)
    if slugs is None:
        return _text("Snapshot does not exist", 404)
    body = {"status": "running", "snapshot_id": snapshot_id, "dataset_id": DATASET_ID}
    if snapshot_id not in _ASKED:
        _ASKED.add(snapshot_id)
        body["running_time"] = COLLECTION_MS // 3
        return body
    records = _records(slugs)
    errors = sum(1 for record in records if "error" in record)
    body["status"] = "ready"
    if errors:
        body["error_codes"] = {"dead_page": errors}
    body.update(
        {
            "records": len(records) - errors,
            "errors": errors,
            "collection_duration": COLLECTION_MS,
            "avg_duration_per_input": COLLECTION_MS // len(slugs),
        }
    )
    return body


@router.get("/datasets/v3/snapshot/{snapshot_id}")
async def snapshot(request: Request, snapshot_id: str):
    denied = _denied(request)
    if denied:
        return denied
    slugs = _slugs(snapshot_id)
    if slugs is None:
        return _text("Snapshot does not exist", 404)
    if snapshot_id not in _ASKED:
        return JSONResponse(
            {
                "status": "running",
                "message": "Snapshot is not ready yet, try again in 30s",
            },
            status_code=202,
        )
    return _records(slugs)
