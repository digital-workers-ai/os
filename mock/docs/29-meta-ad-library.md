# Meta Ad Library API

## Overview

The Ad Library API is the public, read-only face of Meta's ad archive: every ad that ran on Facebook or Instagram, searchable by the page that ran it. OS uses it to keep competitors' ads as they arrived, so a page id is all a competitor needs to be followed.

- **Category:** Competitors
- **Production Base URL:** `https://graph.facebook.com/v25.0`
- **Mock Base URL:** `http://mock:8100/meta-ad-library/v25.0` (from the host: `http://localhost:9192/meta-ad-library/v25.0`)
- **API Version:** v25.0
- **Response Format:** JSON

## Authentication

The same Graph API mechanism as `04-meta-ads.md`: an access token passed as a **query parameter**. The archive is public, so any app token works; ad-account permissions are not needed.

```
?access_token=EAABsbCS1iHgBAxxxxxx
```

Any non-empty `access_token` is accepted by the mock.

---

## Endpoints

### 1. Page lookup

```
GET /v25.0/{page_id}
```

Resolves the page that ran the ads to a name and a website. The website is how OS folds the same competitor across sources: its domain is the identity.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `access_token` | string | **required** | Graph token |
| `fields` | string | `id,name` | Comma-separated; `id,name,website` is what OS asks for |

**Example request:**

```bash
curl "https://graph.facebook.com/v25.0/204815000001?access_token=EAAB...&fields=id,name,website"
```

**Example response (200):**

```json
{
  "id": "204815000001",
  "name": "Vidora",
  "website": "https://vidora.ai"
}
```

Only the requested fields come back, plus `id`, as on the real Graph API.

### 2. Ads archive

```
GET /v25.0/ads_archive
```

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `access_token` | string | **required** | Graph token |
| `search_page_ids` | string | **required** | Comma-separated page ids; only ads run by these pages |
| `ad_reached_countries` | string | **required** | JSON array of ISO country codes, e.g. `["US"]` |
| `ad_active_status` | string | `ACTIVE` | `ALL`, `ACTIVE` (no stop time) or `INACTIVE` (has one) |
| `fields` | string | `id,ad_snapshot_url` | Comma-separated ad fields, listed below |
| `limit` | integer | 25 | Results per page |
| `after` | string | — | Pagination cursor |

**Ad fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Archive id of the ad; always returned |
| `page_id` | string | The page that ran it |
| `page_name` | string | That page's name |
| `ad_creative_bodies` | array of string | Body text, one entry per variation |
| `ad_creative_link_titles` | array of string | Headline of the link card |
| `ad_snapshot_url` | string | Renders the creative; carries the caller's token |
| `publisher_platforms` | array of string | `facebook`, `instagram`, ... |
| `ad_delivery_start_time` | string | `YYYY-MM-DD` |
| `ad_delivery_stop_time` | string | `YYYY-MM-DD`; **absent while the ad is running** |

**Example request:**

```bash
curl "https://graph.facebook.com/v25.0/ads_archive?\
access_token=EAAB...&\
search_page_ids=204815000001&\
ad_reached_countries=[\"US\"]&\
ad_active_status=ALL&\
fields=id,page_id,ad_creative_bodies,ad_snapshot_url,ad_delivery_start_time,ad_delivery_stop_time&\
limit=100"
```

**Example response (200):**

```json
{
  "data": [
    {
      "id": "304100000000001",
      "page_id": "204815000001",
      "ad_creative_bodies": [
        "Hiring a creator vs. typing a brief into Vidora: one takes three weeks and a contract, the other takes four minutes."
      ],
      "ad_snapshot_url": "https://www.facebook.com/ads/archive/render_ad/?id=304100000000001&access_token=EAAB...",
      "ad_delivery_start_time": "2026-06-12"
    },
    {
      "id": "304100000000003",
      "page_id": "204815000001",
      "ad_creative_bodies": [
        "\"We replaced a $9k monthly retainer with Vidora and our cost per purchase dropped 31%.\" A growth lead at a skincare brand, three months in."
      ],
      "ad_snapshot_url": "https://www.facebook.com/ads/archive/render_ad/?id=304100000000003&access_token=EAAB...",
      "ad_delivery_start_time": "2026-08-19",
      "ad_delivery_stop_time": "2026-08-30"
    }
  ],
  "paging": {
    "cursors": {
      "before": "MAZDZD",
      "after": "MjQZD"
    }
  }
}
```

The first ad is running, so it has no `ad_delivery_stop_time` key at all. Meta omits the key rather than sending `null`; a reader that wants "still running" checks for absence.

---

## Pagination

Cursor-based, exactly as `04-meta-ads.md`: follow `paging.cursors.after` while `paging.next` is present. On the last page `paging.cursors` is still there but `next` is not.

---

## Error Responses

### Missing access token (400)

The shared Graph helper answers with the `OAuthException` (code 190) body under FastAPI's `detail` key.

### Unknown page (404)

```json
{
  "error": {
    "message": "Unsupported get request. Object with ID '999' does not exist, cannot be loaded due to missing permissions, or does not support this operation.",
    "type": "GraphMethodException",
    "code": 100
  }
}
```

### Missing required parameter (422)

`search_page_ids` and `ad_reached_countries` are required; the mock refuses their absence with FastAPI's validation body rather than Graph's `(#100)` error.

---

## What the mock simplifies

- The archive holds only the competitors in `world.py`: three pages, seven ads. `ad_reached_countries` is accepted and ignored, every ad reached the US.
- `ad_snapshot_url` embeds whatever token the caller sent, as the real API does, so a captured fixture carries the capture's token.
- No `ad_creative_link_captions`, `ad_creative_link_descriptions`, spend or impression ranges, demographic or regional distributions, and no `search_terms` full-text search; `search_page_ids` is the only selector.
- `page_id` and `page_name` are returned only when asked for in `fields`, like everything but `id`.

---

## Reference

- [Ad Library API](https://www.facebook.com/ads/library/api/) -- Access, parameters and the fields an archived ad exposes
- [ads_archive reference](https://developers.facebook.com/docs/graph-api/reference/ads_archive/) -- Full parameter and field list for the archive edge
- [Graph API pagination](https://developers.facebook.com/docs/graph-api/results) -- Cursor semantics shared with the Marketing API
