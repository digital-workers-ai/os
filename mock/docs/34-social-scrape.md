# Social Scrape — LinkedIn Posts

## Overview

LinkedIn has no public API for reading another company's posts, so companies buy a scraper. BrightData and Apify both sell a LinkedIn company-posts collector: you give it a company and it returns the posts with their engagement counts. OS uses it to see what a competitor is saying in public and which of it landed.

- **Category:** Competitors
- **Production Base URL:** vendor-specific, e.g. `https://api.brightdata.com/datasets/v3`
- **Mock Base URL:** `http://mock:8100/social-scrape` (from the host: `http://localhost:9192/social-scrape`)
- **API Version:** v1
- **Response Format:** JSON

### The prefix and the source name differ

The mock mounts this at `/social-scrape`, because the vendor is a general social scraper and LinkedIn is one collector it runs. The connector declares its source as **`linkedin_posts`**, because that is what the rows are, and a second network would be a second source against the same vendor. Fixtures are named for the source, not the prefix, so the capture lives in `app/backend/fixtures/mock/linkedin_posts/` — the directory name has to equal the source name the connector declares or the replay never finds it.

## Authentication

Bearer token, through the shared `require_bearer` helper in `helpers.py`.

```
Authorization: Bearer mock_linkedin_posts_token
```

Any non-empty bearer token is accepted. A missing or malformed one answers `401` with FastAPI's `detail` body rather than this vendor's envelope; every other error uses the envelope below.

---

## Endpoints

### 1. Posts for one company

```
GET /v1/posts
```

The company is addressed by domain, which is how OS folds a competitor across all six sources.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `domain` | string | **required** | A tracked competitor's domain, no scheme |
| `limit` | integer | — | 1-100; the most recent N. Omit for all of them |

**Example request:**

```bash
curl -G "http://localhost:9192/social-scrape/v1/posts" \
  -H "Authorization: Bearer mock_linkedin_posts_token" \
  --data-urlencode "domain=vidora.ai"
```

**Example response (200):**

```json
{
  "posts": [
    {
      "id": "7241000000000000003",
      "url": "https://www.linkedin.com/feed/update/urn:li:activity:7241000000000000003/",
      "text": "Nine hooks that kept winning across 4,000 ads our customers shipped this year. Swipe through — 9 slides, one hook each, with the ad that proved it and the number it moved. Slide 6 is the one nobody believes until they run it.",
      "posted_at": "2026-08-13T08:20:00Z",
      "reactions": 1180,
      "comments": 147,
      "reposts": 42,
      "platform": "linkedin"
    }
  ],
  "cursor": null
}
```

**Post fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | The LinkedIn activity id, 19 digits |
| `url` | string | The public permalink |
| `text` | string | The post body |
| `posted_at` | string | ISO 8601 |
| `reactions` | integer | Likes and every other reaction, summed |
| `comments` | integer | Comment count |
| `reposts` | integer | Repost count |
| `platform` | string | Always `linkedin` here |

Posts come back newest first, which is what `limit` is for.

`reactions` is ground truth in `world.py`; `comments` and `reposts` are derived from it with `item_factor` and `day_factor`, so they are plausible, proportionate and identical on every call.

---

## Pagination

None. `cursor` is always `null`. Six posts per company is one response; a real collector pages a year of them and a connector that ignores `cursor` from the start would silently take the first page as the whole history.

---

## Error Responses

### Missing or malformed bearer token (401)

```json
{ "detail": "Unauthorized" }
```

### Domain not in the collector's input (404)

```json
{
  "error": {
    "type": "record-not-found",
    "message": "Domain 'example.com' is not in this collector's input."
  }
}
```

### Missing required parameter (422)

`domain` is required; the mock refuses its absence with FastAPI's validation body.

---

## What the connector stores

A post row does not name the company it came from, so the connector carries the request's subject down as `_domain`, under the same leading-underscore convention as the other competitor sources. The stored `source_id` is the post `id`. Captured in `app/backend/fixtures/mock/linkedin_posts/posts.json`: one call per competitor, eighteen rows.

---

## What the mock simplifies

- Three domains, six posts each, spread across 16 July to 11 September 2026. Any other domain is a 404.
- Every company has one carousel among its six, and it is the one that did well — Vidora's nine-hook carousel at 1,180 reactions against a median of about 365. The carousel is visible only in the text, because the field set has no format: a real collector reports the document attachment separately and this one does not.
- No author, no company page metadata, no images or documents, no comment bodies, no reaction breakdown by type, no hashtags, no `is_repost`, and no other network. `platform` is in the shape because the vendor runs collectors for several, and this is the one OS buys.
- No scraping job lifecycle. A real BrightData or Apify run is trigger, poll, download; this is one GET that answers immediately.
- Engagement never moves, so a re-run on a later day produces the same numbers rather than a growth curve.

---

## Reference

- [BrightData LinkedIn datasets](https://docs.brightdata.com/datasets/overview) -- Collector input, trigger-and-poll lifecycle, output fields
- [Apify LinkedIn scrapers](https://docs.apify.com/api/v2) -- Actor runs, dataset items, the `error.type` envelope
- [LinkedIn share urns](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/ugc-post-api) -- Where the `urn:li:activity:` id in the permalink comes from
