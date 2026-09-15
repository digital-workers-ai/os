# Google Ads Transparency Center (via SerpApi)

## Overview

Google's Ads Transparency Center lists every ad an advertiser has run on Search, YouTube and Display, keyed by a public advertiser id. **Google publishes no official API for it**; the center is a web app. SerpApi's `google_ads_transparency_center` engine scrapes it into JSON, and that JSON is the stand-in contract OS builds against: the mock speaks SerpApi's shape, and a real deployment would point `SERPAPI` credentials at `serpapi.com`.

- **Category:** Competitors
- **Production Base URL:** `https://serpapi.com`
- **Mock Base URL:** `http://mock:8100/serpapi` (from the host: `http://localhost:9192/serpapi`)
- **Response Format:** JSON

## Authentication

An API key as a **query parameter**:

```
?api_key=64e1c0f8...
```

Any non-empty `api_key` is accepted by the mock.

---

## Endpoints

### 1. Search

```
GET /search
```

One endpoint for every SerpApi engine; `engine` picks the transparency center and `advertiser_id` picks the advertiser.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | string | **required** | SerpApi key |
| `engine` | string | **required** | Must be `google_ads_transparency_center` |
| `advertiser_id` | string | — | The `AR...` id from the center's URL |
| `creative_format` | string | — | `text`, `image` or `video`; all formats when absent |
| `next_page_token` | string | — | Pagination token from the previous page |

**Example request:**

```bash
curl "https://serpapi.com/search?\
engine=google_ads_transparency_center&\
advertiser_id=AR11111111111111111111&\
api_key=64e1c0f8..."
```

**Example response (200):**

```json
{
  "search_metadata": {
    "status": "Success"
  },
  "search_parameters": {
    "engine": "google_ads_transparency_center",
    "advertiser_id": "AR11111111111111111111"
  },
  "ad_creatives": [
    {
      "advertiser_id": "AR11111111111111111111",
      "advertiser": "Vidora",
      "ad_id": "CR30410000000000000004",
      "format": "text",
      "link": "https://adstransparency.google.com/advertiser/AR11111111111111111111/creative/CR30410000000000000004",
      "target_domain": "vidora.ai",
      "first_shown": 1784678400,
      "last_shown": 1788393600,
      "text": "What if every product page came with its own video ad? Vidora turns a URL into a scripted, voiced, captioned ad in minutes."
    }
  ],
  "serpapi_pagination": {
    "next_page_token": "MQ=="
  }
}
```

**Creative fields:**

| Field | Type | Description |
|-------|------|-------------|
| `advertiser_id` | string | The advertiser queried |
| `advertiser` | string | Display name of the advertiser |
| `ad_id` | string | `CR` followed by digits; the creative's id in the center |
| `format` | string | `text`, `image` or `video` |
| `link` | string | The creative's page in the transparency center |
| `target_domain` | string | Where the ad sends people; the advertiser's own domain |
| `first_shown` | integer | Unix seconds of the first day the ad was seen |
| `last_shown` | integer | Unix seconds of the last day it was seen; recent for a running ad |
| `text` | string | Body copy; **only present on `text` creatives** |
| `image` | string | Rendered creative; only on `image` creatives |
| `video` | string | Embedded video; only on `video` creatives |

The center shows image and video creatives as pictures, not words, so the listing carries no copy for them. A reader that wants a name for every ad only gets one for text creatives.

There is no advertiser endpoint. The advertiser's name and domain come with every creative, and OS builds its one advertiser record from them.

---

## Pagination

Token-based: while `serpapi_pagination.next_page_token` is present, repeat the request with it as `next_page_token`. The last page carries an empty `serpapi_pagination`. The mock serves one creative per page so every advertiser with more than one creative exercises the walk.

---

## Error Responses

### Missing API key (401)

```json
{
  "error": "Invalid API key. Your API key should be here: https://serpapi.com/manage-api-key"
}
```

### Wrong engine (400)

```json
{
  "error": "Unsupported `google_ads` engine."
}
```

### Unknown advertiser (200)

SerpApi answers a search with no results with a 200 and an error string, not a 404:

```json
{
  "error": "Google hasn't returned any results for this query."
}
```

---

## What the mock simplifies

- Only the three advertisers in `world.py` exist, five creatives between them: two text, two image, one video.
- `last_shown` for a running creative is pinned to `2026-09-03` so captures are stable; SerpApi would report the day of the query.
- `search_metadata` carries only `status`; the real one adds ids, timestamps and endpoint links. `search_parameters` echoes only `engine` and `advertiser_id`.
- No `region`, `topic`, `political_ads`, `start_date` or `end_date` filters; no `width`, `height` or `days_ran_for` on creatives.

---

## Reference

- [Ads Transparency Center](https://adstransparency.google.com/) -- The web app; no API of its own
- [SerpApi: Google Ads Transparency Center API](https://serpapi.com/google-ads-transparency-center-api) -- Parameters, the `ad_creatives` shape and pagination
- [SerpApi: errors](https://serpapi.com/search-api#api-errors) -- Status codes and error bodies
