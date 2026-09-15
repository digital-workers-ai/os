# Google Ads Transparency Center (via SerpApi)

## Overview

Google's Ads Transparency Center lists every ad an advertiser has run on Search, YouTube and Display, keyed by a public advertiser id. **Google publishes no official API for it**; the center is a web app. SerpApi's `google_ads_transparency_center` engine scrapes it into JSON, and that JSON is the stand-in contract OS builds against: the mock speaks SerpApi's shape, and a real deployment would point `SERPAPI` credentials at `serpapi.com`.

- **Category:** Competitors
- **Production Base URL:** `https://serpapi.com`
- **Mock Base URL:** `http://mock:8100/serpapi` (from the host: `http://localhost:8192/serpapi`)
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
      "ad_creative_id": "CR30410000000000000004",
      "format": "text",
      "width": 300,
      "height": 250,
      "first_shown": 1784678400,
      "last_shown": 1788393600,
      "total_days_shown": 44,
      "details_link": "https://adstransparency.google.com/advertiser/AR11111111111111111111/creative/CR30410000000000000004?region=anywhere",
      "serpapi_details_link": "https://serpapi.com/search.json?engine=google_ads_transparency_center_details&advertiser_id=AR11111111111111111111&creative_id=CR30410000000000000004",
      "target_domain": "vidora.ai"
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
| `ad_creative_id` | string | `CR` followed by digits; the creative's id in the center |
| `format` | string | `text`, `image` or `video` |
| `width` | integer | Rendered width in pixels |
| `height` | integer | Rendered height in pixels |
| `first_shown` | integer | Unix seconds of the first day the ad was seen |
| `last_shown` | integer | Unix seconds of the last day it was seen; recent for a running ad |
| `total_days_shown` | integer | Days between the two, inclusive |
| `details_link` | string | The creative's page in the transparency center |
| `serpapi_details_link` | string | SerpApi's details engine for this creative, which renders it |
| `target_domain` | string | Where the ad sends people; **absent on some creatives** |
| `image` | string | Rendered creative; only on `image` creatives |

The listing carries no copy at all, not even for text creatives: the center renders every creative as a picture, and the words live behind `details_link`. OS therefore names Google creatives by nothing and shows them by their `details_link`.

There is no advertiser endpoint. The advertiser's name comes with every creative and its domain with most of them, so OS builds its one advertiser record from the first creative's `advertiser` and the first `target_domain` it finds; when no creative carries one, the domain is the one the competitors file gives that advertiser.

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
- `last_shown` for a running creative is pinned to `2026-09-03` so captures are stable, and `total_days_shown` is counted from it; SerpApi would report the day of the query.
- `target_domain` is omitted on image creatives, the way the center leaves it off some real ones, so Avatarly's only Google creative names no domain and its advertiser record falls back to the file.
- `width` and `height` are fixed per format rather than read from the creative.
- `search_metadata` carries only `status`; the real one adds ids, timestamps and endpoint links. `search_parameters` echoes only `engine` and `advertiser_id`.
- No `region`, `topic`, `political_ads`, `start_date` or `end_date` filters, and no details engine behind `serpapi_details_link`.

---

## Reference

- [Ads Transparency Center](https://adstransparency.google.com/) -- The web app; no API of its own
- [SerpApi: Google Ads Transparency Center API](https://serpapi.com/google-ads-transparency-center-api) -- Parameters, the `ad_creatives` shape and pagination
- [SerpApi: errors](https://serpapi.com/search-api#api-errors) -- Status codes and error bodies
