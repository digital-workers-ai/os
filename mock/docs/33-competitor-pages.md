# Competitor Pages — Crawl

## Overview

A crawl stand-in: list a competitor's pages, then fetch each one as text with a hash of that text. OS keeps the hash so it can tell when a page changed, which is the whole point of the source — a competitor's pricing page moving from $99 to $79 is a thing the marketer agent should notice the morning it happens.

Firecrawl, Diffbot and ScrapingBee all sell this shape. The contract below is close to Firecrawl's, trimmed to the two calls a change monitor makes.

- **Category:** Competitors
- **Production Base URL:** vendor-specific, e.g. `https://api.firecrawl.dev`
- **Mock Base URL:** `http://mock:8100/pages` (from the host: `http://localhost:9192/pages`)
- **API Version:** v1
- **Response Format:** JSON

## Authentication

Bearer token, through the shared `require_bearer` helper in `helpers.py`.

```
Authorization: Bearer mock_competitor_pages_token
```

Any non-empty bearer token is accepted. A missing or malformed one answers `401` with FastAPI's `detail` body rather than this vendor's envelope; every other error uses the envelope below.

---

## Endpoints

### 1. Sitemap

```
GET /v1/sitemap
```

The pages worth watching on one domain. A monitor calls this first, then fetches each URL.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `domain` | string | **required** | A tracked competitor's domain, no scheme |

**Example request:**

```bash
curl -G "http://localhost:9192/pages/v1/sitemap" \
  -H "Authorization: Bearer mock_competitor_pages_token" \
  --data-urlencode "domain=vidora.ai"
```

**Example response (200):**

```json
{
  "domain": "vidora.ai",
  "urls": [
    "https://vidora.ai/",
    "https://vidora.ai/pricing",
    "https://vidora.ai/how-it-works",
    "https://vidora.ai/blog",
    "https://vidora.ai/blog/one-url-thirty-ads",
    "https://vidora.ai/blog/what-a-creator-brief-costs",
    "https://vidora.ai/about"
  ]
}
```

`urls` holds absolute URLs, which is what a sitemap carries and what `/v1/fetch` takes.

### 2. Fetch

```
GET /v1/fetch
```

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | string | **required** | One of the URLs the sitemap listed |
| `as_of` | string | today | `YYYY-MM-DD`; picks which stored version comes back |

**Example request:**

```bash
curl -G "http://localhost:9192/pages/v1/fetch" \
  -H "Authorization: Bearer mock_competitor_pages_token" \
  --data-urlencode "url=https://vidora.ai/pricing"
```

**Example response (200):**

```json
{
  "url": "https://vidora.ai/pricing",
  "title": "Pricing — Vidora",
  "text": "Three plans, no per-render fees. ...\n\nStudio — $99 a month. Unlimited ads, 1080p, no watermark, three brand kits and one seat. This is the plan most teams stay on.\n\n...",
  "fetched_at": "2026-09-14T05:50:00Z",
  "content_sha": "d9f5d1353c6ae4c3...",
  "word_count": 194
}
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `url` | string | The page, normalised to `https://domain/path` |
| `title` | string | The page's title |
| `text` | string | The page's copy, paragraphs joined with a blank line |
| `fetched_at` | string | ISO 8601; the mock puts `as_of` at 05:50 UTC |
| `content_sha` | string | `sha256` of `text`, hex — the change signal |
| `word_count` | integer | Words in `text` |

### The page that changes

Change detection is what this source is for, so one page has two versions. Vidora's `/pricing` is stored twice: the version now, and a revision that takes effect on **2026-09-18**.

The mock picks by `as_of`: the latest revision whose effective date is on or before `as_of`, and otherwise the base version. With no `as_of` you get the version live today.

```bash
# today: Studio is $99, three brand kits, one seat
curl -G .../v1/fetch --data-urlencode "url=https://vidora.ai/pricing"

# on or after 2026-09-18: Studio is $79, five brand kits, two seats
curl -G .../v1/fetch --data-urlencode "url=https://vidora.ai/pricing" \
                     --data-urlencode "as_of=2026-09-20"
```

`content_sha` differs between the two, as do `title`-adjacent copy, `word_count` and `fetched_at`. Nothing else on any other page moves.

The real crawler has no `as_of`. It fetches what is live and the monitor finds the change by comparing today's `content_sha` against the one it stored yesterday. `as_of` exists so a test can reach the second version without waiting for a date to arrive, and a connector should not send it in normal operation.

---

## Pagination

None. A sitemap is one response and a fetch is one page. Real crawlers paginate large sitemaps with a cursor; seven pages per domain never needs it.

---

## Error Responses

### Missing or malformed bearer token (401)

```json
{ "detail": "Unauthorized" }
```

### Domain not tracked (404)

```json
{ "success": false, "error": "No crawl configured for domain 'example.com'" }
```

### URL not in the sitemap (404)

```json
{ "success": false, "error": "No capture for https://vidora.ai/nope" }
```

### `as_of` is not a date (400)

```json
{ "success": false, "error": "as_of must be an ISO date, got 'soon'" }
```

### Missing required parameter (422)

`domain` and `url` are required; the mock refuses their absence with FastAPI's validation body.

---

## What the connector stores

The fetch response already names its own subject, so nothing is added to it. The stored `source_id` is the `url`, one row per page, and re-crawling the same page on a later day overwrites the row rather than appending — the history lives in the `content_sha` the pipeline keeps, not in duplicate raw rows. Captured in `app/backend/fixtures/mock/competitor_pages/pages.json`: a sitemap call for each of the three competitors, then a fetch for every URL it returned, twenty-one rows.

---

## What the mock simplifies

- Three domains, seven pages each: `/`, `/pricing`, `/how-it-works`, `/blog`, two blog posts and `/about`. Any other URL is a 404.
- `text` is the page's own copy followed by the site's shared footer, which is what a crawl of a real page returns — navigation and legal boilerplate included, on every page of the site.
- No HTML, no markdown, no screenshots, no links graph, no `robots.txt` handling, no rendering of JavaScript, no rate limiting and no crawl jobs. One GET is one page.
- One page has a second version and the rest never move, so a change-detection test has exactly one thing to find.
- `fetched_at` is derived from `as_of` rather than the clock, so repeated calls are byte-identical.

---

## Reference

- [Firecrawl](https://docs.firecrawl.dev/api-reference/introduction) -- Scrape and map endpoints; the closest public shape to this one
- [Diffbot](https://docs.diffbot.com/reference/article) -- Article extraction, text plus metadata
- [ScrapingBee](https://www.scrapingbee.com/documentation/) -- HTML API with rendering options
