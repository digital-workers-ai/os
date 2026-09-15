from datetime import date
from urllib.parse import urlsplit

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from seeds.helpers import require_bearer
from seeds.world import (
    COMPETITOR_PAGE_REVISIONS_BY_PAGE,
    COMPETITOR_PAGES_BY_COMPETITOR,
    COMPETITOR_SITE_FOOTERS,
    COMPETITORS_BY_DOMAIN,
)

router = APIRouter()

_TODAY = "2026-09-14"
_MAP_LIMIT = 100


def _failed(status, message):
    return JSONResponse(status_code=status, content={"success": False, "error": message})


def _split(url):
    parts = urlsplit(url if "://" in url else f"https://{url}")
    return (parts.hostname or "").removeprefix("www."), parts.path or "/"


def _version(page, as_of):
    title, paragraphs = page.title, page.paragraphs
    for revision in COMPETITOR_PAGE_REVISIONS_BY_PAGE.get(page.id, []):
        if revision.effective_from <= as_of:
            title, paragraphs = revision.title, revision.paragraphs
    return title, paragraphs


def _page_at(competitor, path):
    for page in COMPETITOR_PAGES_BY_COMPETITOR.get(competitor.id, []):
        if page.path == path:
            return page
    return None


def _description(paragraphs):
    return paragraphs[0].split(". ")[0].rstrip(".") + "." if paragraphs else ""


async def _body(request):
    try:
        body = await request.json()
    except ValueError:
        return None
    return body if isinstance(body, dict) else None


@router.post("/v2/map")
async def map_site(request: Request):
    require_bearer(request)
    body = await _body(request)
    url = (body or {}).get("url")
    if not isinstance(url, str) or not url:
        return _failed(400, "Bad Request: url is required")
    domain, _path = _split(url)
    competitor = COMPETITORS_BY_DOMAIN.get(domain)
    if competitor is None:
        return _failed(404, f"No site mapped for {url}")
    limit = body.get("limit") or _MAP_LIMIT
    return {
        "success": True,
        "links": [
            {
                "url": f"https://{domain}{page.path}",
                "title": page.title,
                "description": _description(page.paragraphs),
            }
            for page in COMPETITOR_PAGES_BY_COMPETITOR[competitor.id][:limit]
        ],
    }


@router.post("/v2/scrape")
async def scrape(request: Request, as_of: str = Query(_TODAY)):
    require_bearer(request)
    try:
        date.fromisoformat(as_of)
    except ValueError:
        return _failed(400, f"as_of must be an ISO date, got '{as_of}'")
    body = await _body(request)
    url = (body or {}).get("url")
    if not isinstance(url, str) or not url:
        return _failed(400, "Bad Request: url is required")
    domain, path = _split(url)
    competitor = COMPETITORS_BY_DOMAIN.get(domain)
    page = _page_at(competitor, path) if competitor is not None else None
    if page is None:
        return _failed(404, f"No capture for {url}")
    title, paragraphs = _version(page, as_of)
    parts = [f"# {title}", *paragraphs]
    if not body.get("onlyMainContent"):
        parts.append(COMPETITOR_SITE_FOOTERS[competitor.id])
    source_url = f"https://{domain}{path}"
    return {
        "success": True,
        "data": {
            "markdown": "\n\n".join(parts),
            "metadata": {
                "title": title,
                "description": _description(paragraphs),
                "sourceURL": source_url,
                "url": source_url,
                "statusCode": 200,
            },
        },
    }
