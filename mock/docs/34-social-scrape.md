# Social Scrape — BrightData LinkedIn Posts

## Overview

LinkedIn has no public API for reading another company's posts, so companies buy a scraper. BrightData sells a LinkedIn posts dataset: you trigger a collection with a company page URL, poll until the snapshot is ready, then download the posts with their engagement counts. OS uses it to see what a competitor is saying in public and which of it landed.

The contract is BrightData's datasets v3 lifecycle: trigger, progress, snapshot.

- **Category:** Competitors
- **Production Base URL:** `https://api.brightdata.com`
- **Mock Base URL:** `http://mock:8100/social-scrape` (from the host: `http://localhost:8192/social-scrape`)
- **API Version:** datasets v3
- **Response Format:** JSON

### The prefix and the source name differ

The mock mounts this at `/social-scrape`, because the vendor is a general scraper and LinkedIn posts are one dataset it runs. The connector declares its source as **`linkedin_posts`**, because that is what the rows are, and a second network would be a second source against the same vendor. Fixtures are named for the source, not the prefix, so the capture lives in `app/backend/fixtures/mock/linkedin_posts/` — the directory name has to equal the source name the connector declares or the replay never finds it.

## Authentication

Bearer token, through the shared `require_bearer` helper in `helpers.py`.

```
Authorization: Bearer mock_linkedin_posts_token
```

Any non-empty bearer token is accepted. A missing or malformed one answers `401` with FastAPI's `detail` body rather than this vendor's envelope; every other error uses the envelope below.

---

## Endpoints

### 1. Trigger a collection

```
POST /datasets/v3/trigger
```

Starts a snapshot for the companies in the body and answers at once with its id.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `dataset_id` | string | **required** | `gd_lyy3tktm25m4avu764`, the LinkedIn posts dataset |
| `type` | string | `discover_new` | The only collection type this dataset runs |
| `discover_by` | string | **required** | `company_url`: find the posts from the company page |
| `format` | string | `json` | The only format served |
| `include_errors` | boolean | false | Accepted and ignored; the mock has no per-row errors |

**Request body:** a list of inputs, one per company.

| Field | Type | Description |
|-------|------|-------------|
| `url` | string | A tracked competitor's LinkedIn company page, `https://www.linkedin.com/company/<slug>` |

**Example request:**

```bash
curl -X POST "http://localhost:8192/social-scrape/datasets/v3/trigger?dataset_id=gd_lyy3tktm25m4avu764&type=discover_new&discover_by=company_url&format=json&include_errors=true" \
  -H "Authorization: Bearer mock_linkedin_posts_token" \
  -H "Content-Type: application/json" \
  -d '[{"url": "https://www.linkedin.com/company/vidora"}]'
```

**Example response (200):**

```json
{ "snapshot_id": "s_000001_k1" }
```

### 2. Progress of a snapshot

```
GET /datasets/v3/progress/{snapshot_id}
```

**Example request:**

```bash
curl "http://localhost:8192/social-scrape/datasets/v3/progress/s_000001_k1" \
  -H "Authorization: Bearer mock_linkedin_posts_token"
```

**Example response (200):**

```json
{ "snapshot_id": "s_000001_k1", "dataset_id": "gd_lyy3tktm25m4avu764", "status": "running" }
```

`status` is `running` on the first poll of a snapshot and `ready` on every poll after it. BrightData also reports `failed`, which the mock never produces; a connector should treat it as final and read nothing.

### 3. Download a snapshot

```
GET /datasets/v3/snapshot/{snapshot_id}
```

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `format` | string | `json` | The only format served |

**Example request:**

```bash
curl "http://localhost:8192/social-scrape/datasets/v3/snapshot/s_000001_k1?format=json" \
  -H "Authorization: Bearer mock_linkedin_posts_token"
```

**Example response (200):** a JSON array, newest post first.

```json
[
  {
    "url": "https://www.linkedin.com/posts/vidora_activity-7241000000000000003",
    "id": "7241000000000000003",
    "user_id": "https://www.linkedin.com/company/vidora",
    "post_text": "Nine hooks that kept winning across 4,000 ads our customers shipped this year. Swipe through — 9 slides, one hook each, with the ad that proved it and the number it moved. Slide 6 is the one nobody believes until they run it.",
    "date_posted": "2026-08-13T08:20:00.000Z",
    "hashtags": ["#vidora", "#ugc"],
    "num_likes": 1180,
    "num_comments": 147,
    "num_shares": 42,
    "post_type": "document",
    "user_followers": 18400
  }
]
```

**Post fields:**

| Field | Type | Description |
|-------|------|-------------|
| `url` | string | The public permalink |
| `id` | string | The LinkedIn activity id, 19 digits |
| `user_id` | string | The company page the post was collected from |
| `post_text` | string | The post body |
| `date_posted` | string | ISO 8601 with milliseconds |
| `hashtags` | list | Hashtags in the post |
| `num_likes` | integer | Reactions of every kind, summed |
| `num_comments` | integer | Comment count |
| `num_shares` | integer | Repost count |
| `post_type` | string | `post`, or `document` for a carousel |
| `user_followers` | integer | The company page's followers when collected |

Asked for before the progress has reached `ready`, the snapshot answers `202` with `{"status": "running", ...}` and no rows, which is what BrightData does.

`num_likes` is ground truth in `world.py`; `num_comments` and `num_shares` are derived from it with `item_factor` and `day_factor`, so they are plausible, proportionate and identical on every call.

---

## Pagination

None. A snapshot is one array. BrightData pages large snapshots with `batch_size` and `part`; six posts per company is one download.

---

## Error Responses

### Missing or malformed bearer token (401)

```json
{ "detail": "Unauthorized" }
```

### Unknown dataset (404)

```json
{ "error": "Dataset gd_nope not found" }
```

### Wrong collection type or discovery (400)

```json
{ "error": "This dataset is discovered by company_url only" }
```

### Body is not a list of inputs (400)

```json
{ "error": "Input must be a non-empty list of objects with a url" }
```

### Company page not tracked (400)

```json
{ "error": "No LinkedIn company page known for https://www.linkedin.com/company/example" }
```

### Unknown snapshot (404)

```json
{ "error": "Snapshot s_nope not found" }
```

### Missing required parameter (422)

`dataset_id` and `discover_by` are required; the mock refuses their absence with FastAPI's validation body.

---

## What the connector stores

One trigger per tracked competitor, with the company page from `competitors.yaml` as the single input; then progress polled up to `MAX_POLLS` times with a sleep between polls and none before the first; then, on `ready`, the snapshot read as json. A post row does not name the company it came from, so the connector carries the competitor's domain down as `_competitor_ref`, under the same leading-underscore convention as the other competitor sources. The stored `source_id` is the post `id`, or its `url` when the id is absent. A snapshot that reports `failed` is counted under `failed_snapshots`; one that never reaches `ready` within the poll budget is counted under `unfinished_snapshots`; neither stores anything. Captured in `app/backend/fixtures/mock/linkedin_posts/posts.json`: one collection per competitor, eighteen rows.

---

## What the mock simplifies

- Three company pages, six posts each, spread across 16 July to 11 September 2026. Any other company page is refused at the trigger rather than reported as a row error in the snapshot.
- Every company has one carousel among its six, marked `post_type: document`, and it is the one that did well — Vidora's nine-hook carousel at 1,180 reactions against a median of about 365.
- The lifecycle is real but short: one `running` poll, then `ready`, then the download. No `failed`, no partial snapshots, no `batch_size`, no delivery to storage, no webhooks and no cost accounting.
- Snapshot state lives in the mock process, so a restart forgets every snapshot id it issued.
- No author beyond the company page, no images or documents, no comment bodies, no reaction breakdown by type, no `is_repost`, and no other network.
- Engagement never moves, so a re-run on a later day produces the same numbers rather than a growth curve.

---

## Reference

- [BrightData trigger](https://docs.brightdata.com/api-reference/web-scraper-api/trigger-a-collection) -- `dataset_id`, `type`, `discover_by` and the input list
- [BrightData progress and snapshot](https://docs.brightdata.com/api-reference/web-scraper-api/monitor-progress) -- The status values and the snapshot download
- [BrightData LinkedIn posts dataset](https://brightdata.com/products/web-scraper/linkedin/posts) -- The output fields this mock reproduces
