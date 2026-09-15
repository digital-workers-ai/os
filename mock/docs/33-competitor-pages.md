# Competitor Pages — Firecrawl v2

## Overview

A change monitor for competitors' sites: map a domain to the pages worth reading, then scrape each one to markdown and keep a hash of it. OS keeps the hash so it can tell when a page changed, which is the whole point of the source — a competitor's pricing page moving from $99 to $79 is a thing the marketer agent should notice the morning it happens.

The contract is Firecrawl's v2 API, trimmed to the two calls a monitor makes: `map` for the site and `scrape` for a page.

- **Category:** Competitors
- **Production Base URL:** `https://api.firecrawl.dev`
- **Mock Base URL:** `http://mock:8100/pages` (from the host: `http://localhost:8192/pages`)
- **API Version:** v2
- **Response Format:** JSON

## Authentication

Bearer token, through the shared `require_bearer` helper in `helpers.py`.

```
Authorization: Bearer mock_competitor_pages_token
```

Any non-empty bearer token is accepted. A missing or malformed one answers `401` with FastAPI's `detail` body rather than this vendor's envelope; every other error uses the envelope below.

---

## Endpoints

### 1. Map

```
POST /v2/map
```

The pages on one site. A monitor calls this first, then scrapes each link.

**Request body:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | string | **required** | The site, with or without a scheme; `www.` is ignored |
| `limit` | integer | 100 | Most links to return |
| `includeSubdomains` | boolean | true | Whether pages on the site's subdomains are listed too |

**Example request:**

```bash
curl -X POST "http://localhost:8192/pages/v2/map" \
  -H "Authorization: Bearer mock_competitor_pages_token" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://vidora.ai", "limit": 50, "includeSubdomains": false}'
```

**Example response (200):**

```json
{
  "success": true,
  "links": [
    {
      "url": "https://vidora.ai/",
      "title": "Vidora — video ads from a product URL",
      "description": "Paste a product URL."
    },
    {
      "url": "https://vidora.ai/pricing",
      "title": "Pricing — Vidora",
      "description": "Three plans, no per-render fees."
    }
  ]
}
```

`links` holds objects, not bare strings: v2 returns the title and description it saw alongside each URL. The URL is what `/v2/scrape` takes.

With `includeSubdomains` absent or true the map also lists pages on the site's subdomains, which a real map does by default: a product's `app.` or `get.` host is part of the same site to Firecrawl. The connector sends `false`, because a competitor's sign-in page and marketing tools are not the copy the monitor watches.

### 2. Scrape

```
POST /v2/scrape
```

**Request body:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | string | **required** | One of the URLs the map listed |
| `formats` | list | `["markdown"]` | Accepted and ignored; markdown is the only format served |
| `onlyMainContent` | boolean | false | `true` drops the site's navigation and footer from the markdown |

**Query parameters (mock only):**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `as_of` | string | today | `YYYY-MM-DD`; picks which stored version comes back |

**Example request:**

```bash
curl -X POST "http://localhost:8192/pages/v2/scrape" \
  -H "Authorization: Bearer mock_competitor_pages_token" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://vidora.ai/pricing", "formats": ["markdown"], "onlyMainContent": true}'
```

**Example response (200):**

```json
{
  "success": true,
  "data": {
    "markdown": "# Pricing — Vidora\n\nThree plans, no per-render fees. ...\n\nStudio — $99 a month. Unlimited ads, 1080p, no watermark, three brand kits and one seat. This is the plan most teams stay on.\n\n...",
    "metadata": {
      "title": "Pricing — Vidora",
      "description": "Three plans, no per-render fees.",
      "sourceURL": "https://vidora.ai/pricing",
      "url": "https://vidora.ai/pricing",
      "statusCode": 200
    }
  }
}
```

**Fields under `data`:**

| Field | Type | Description |
|-------|------|-------------|
| `markdown` | string | The page as markdown: a title heading, then the copy, paragraphs separated by a blank line |
| `metadata.title` | string | The page's title |
| `metadata.description` | string | The page's meta description |
| `metadata.sourceURL` | string | The URL that was asked for, normalised to `https://domain/path` |
| `metadata.url` | string | The URL that answered; the same here, since nothing redirects |
| `metadata.statusCode` | integer | The site's own status for the page |

There is no hash and no word count in the response. Firecrawl returns the content and leaves the comparing to the caller; the connector's extract hook computes `_body_sha` and `_word_count` from `markdown` on the way in.

### The page that changes

Change detection is what this source is for, so one page has two versions. Vidora's `/pricing` is stored twice: the version now, and a revision that takes effect on **2026-09-18**.

The mock picks by `as_of`: the latest revision whose effective date is on or before `as_of`, and otherwise the base version. With no `as_of` you get the version live today.

Today, Studio is $99 with three brand kits and one seat:

```bash
curl -X POST .../v2/scrape -d '{"url": "https://vidora.ai/pricing"}'
```

On or after 2026-09-18, Studio is $79 with five brand kits and two seats:

```bash
curl -X POST ".../v2/scrape?as_of=2026-09-20" -d '{"url": "https://vidora.ai/pricing"}'
```

The markdown differs between the two, and with it the hash and the word count the hook computes. Nothing else on any other page moves.

Firecrawl has no `as_of`. It scrapes what is live and the monitor finds the change by comparing today's hash against the one it stored yesterday. `as_of` exists so a test can reach the second version without waiting for a date to arrive, and a connector should not send it in normal operation.

---

## Pagination

None. A map is one response and a scrape is one page. Firecrawl caps `map` with `limit` rather than paging it; seven pages per site never reaches the cap.

---

## Error Responses

### Missing or malformed bearer token (401)

```json
{ "detail": "Unauthorized" }
```

### No `url` in the body (400)

```json
{ "success": false, "error": "Bad Request: url is required" }
```

### Site not tracked (404, map)

```json
{ "success": false, "error": "No site mapped for https://example.com" }
```

### URL not on the site (404, scrape)

```json
{ "success": false, "error": "No capture for https://vidora.ai/nope" }
```

### `as_of` is not a date (400)

```json
{ "success": false, "error": "as_of must be an ISO date, got 'soon'" }
```

---

## What the connector stores

One `map` per tracked competitor with `includeSubdomains: false` and `limit` 50, then one `scrape` per link it returned, with `formats: ["markdown"]` and `onlyMainContent: true`. Each successful scrape's `data` object is stored as it arrived, with two stamps added under the leading-underscore convention: `_fetched_at`, the connector's clock at the time of the scrape, and `_competitor_ref`, the tracked competitor's domain from `competitors.yaml`, the way `linkedin_posts` stamps its posts. The domain is not read from the page's URL: a page answered from `www.`, `app.` or any other host under the crawl still belongs to the competitor whose site was mapped, which is the domain the estate folds a competitor on. The stored `source_id` is `metadata.sourceURL`, one row per page; a scrape whose `success` is false or that carries no `data` is counted under `failed_scrapes` and not stored. Captured in `app/backend/fixtures/mock/competitor_pages/pages.json`: twenty-one rows, seven per competitor.

---

## What the mock simplifies

- Three sites, seven pages each: `/`, `/pricing`, `/how-it-works`, `/blog`, two blog posts and `/about`. Any other URL is a 404.
- One subdomain link per site, `https://app.<domain>/login`, is listed only when `includeSubdomains` is absent or true, so a connector that forgets the flag sees a page it should not have asked for. It has no capture: scraping it is a 404.
- `markdown` is a heading and the page's own copy; with `onlyMainContent` false the site's shared footer follows it, which is what a scrape of a real page returns — navigation and legal boilerplate included, on every page of the site.
- No HTML, no screenshots, no links graph, no `robots.txt` handling, no rendering of JavaScript, no rate limiting, no credits and no asynchronous crawl jobs. One POST is one page.
- `formats` is accepted and ignored; markdown is the only format served.
- One page has a second version and the rest never move, so a change-detection test has exactly one thing to find.
- `description` is the first sentence of the page's first paragraph rather than a real meta description.

---

## Reference

- [Firecrawl map](https://docs.firecrawl.dev/api-reference/endpoint/map) -- The v2 map endpoint and its link objects
- [Firecrawl scrape](https://docs.firecrawl.dev/api-reference/endpoint/scrape) -- The v2 scrape endpoint, `formats` and `onlyMainContent`
- [Firecrawl errors](https://docs.firecrawl.dev/api-reference/introduction) -- The `success`/`error` envelope
