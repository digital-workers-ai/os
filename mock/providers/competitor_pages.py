import hashlib
from datetime import date

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

_CRAWLED_AT_TIME = "05:50:00Z"
_TODAY = "2026-09-14"


def _failed(status, message):
    return JSONResponse(status_code=status, content={"success": False, "error": message})


def _split(url):
    without_scheme = url.split("://", 1)[-1]
    domain, _, rest = without_scheme.partition("/")
    return domain, "/" + rest


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


@router.get("/v1/sitemap")
async def sitemap(request: Request, domain: str = Query(...)):
    require_bearer(request)
    competitor = COMPETITORS_BY_DOMAIN.get(domain)
    if competitor is None:
        return _failed(404, f"No crawl configured for domain '{domain}'")
    return {
        "domain": domain,
        "urls": [
            f"https://{domain}{page.path}"
            for page in COMPETITOR_PAGES_BY_COMPETITOR[competitor.id]
        ],
    }


@router.get("/v1/fetch")
async def fetch(request: Request, url: str = Query(...), as_of: str = Query(_TODAY)):
    require_bearer(request)
    try:
        date.fromisoformat(as_of)
    except ValueError:
        return _failed(400, f"as_of must be an ISO date, got '{as_of}'")
    domain, path = _split(url)
    competitor = COMPETITORS_BY_DOMAIN.get(domain)
    if competitor is None:
        return _failed(404, f"No crawl configured for domain '{domain}'")
    page = _page_at(competitor, path)
    if page is None:
        return _failed(404, f"No capture for {url}")
    title, paragraphs = _version(page, as_of)
    text = "\n\n".join([*paragraphs, COMPETITOR_SITE_FOOTERS[competitor.id]])
    return {
        "url": f"https://{domain}{path}",
        "title": title,
        "text": text,
        "fetched_at": f"{as_of}T{_CRAWLED_AT_TIME}",
        "content_sha": hashlib.sha256(text.encode()).hexdigest(),
        "word_count": len(text.split()),
    }
