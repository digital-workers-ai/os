# Meta Marketing API (Facebook/Instagram Ads)

## Overview

The Meta Marketing API (formerly Facebook Marketing API) provides access to ad accounts, campaigns, ad sets, ads, and performance insights across Facebook and Instagram placements. Used by Elise for paid social advertising data.

- **Category:** Social Ads
- **Production Base URL:** `https://graph.facebook.com/v25.0`
- **Mock Base URL:** `http://localhost:8100/meta/v25.0`
- **API Version:** v25.0
- **Response Format:** JSON

## Authentication

Meta uses an OAuth access token passed as a **query parameter** (not a header):

```
?access_token=EAABsbCS1iHgBAxxxxxx
```

All requests must include `access_token` as a query parameter. Requests without it receive an error response (not a 401 status — Meta returns 200 with an error object in some cases).

### Token Types

| Type | Usage | Lifetime |
|------|-------|----------|
| User token | Development, short-lived | 1-2 hours |
| Long-lived user token | Extended access | 60 days |
| System user token | Server-to-server | Does not expire |

### Mock Server Token

Any non-empty `access_token` value is accepted.

---

## Endpoints

### 1. Ad Account Insights

```
GET /v25.0/{ad_account_id}/insights
```

Primary endpoint for fetching ad performance metrics.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `access_token` | string | **required** | OAuth token |
| `fields` | string | — | Comma-separated metric/dimension list |
| `level` | string | `"ad"` | Aggregation level: `"ad"`, `"adset"`, `"campaign"`, `"account"` |
| `time_range` | string | — | JSON string: `{"since":"2026-07-01","until":"2026-07-07"}` |
| `date_preset` | string | `"last_30d"` | Alternative to `time_range`: `"today"`, `"yesterday"`, `"last_7d"`, `"last_14d"`, `"last_28d"`, `"last_30d"`, `"last_90d"`, `"this_month"`, `"last_month"`, `"maximum"`, etc. |
| `time_increment` | integer or string | `"all_days"` | `1`-`90` for daily/N-day buckets, `"monthly"`, or `"all_days"` for aggregate |
| `breakdowns` | string | — | Comma-separated: `"age,gender"`, `"country"`, `"publisher_platform"` |
| `action_attribution_windows` | string | — | JSON array of attribution windows: `["1d_click","7d_click"]`. Values: `1d_view`, `7d_view`, `28d_view`, `1d_click`, `7d_click`, `28d_click`, `dda`, `default`, `skan_view`, `skan_click` |
| `limit` | integer | 25 | Results per page (max 200 for insights) |
| `after` | string | — | Pagination cursor |

**Example request:**

```bash
curl "https://graph.facebook.com/v25.0/act_123456/insights?\
access_token=EAABsbCS1iHgBAxxxxxx&\
fields=campaign_name,impressions,clicks,spend,cpc,ctr,actions&\
level=campaign&\
time_range={\"since\":\"2026-07-01\",\"until\":\"2026-07-07\"}&\
time_increment=1&\
limit=2"
```

**Example response (200):**

```json
{
  "data": [
    {
      "campaign_name": "Summer Sale - Prospecting",
      "campaign_id": "camp_001",
      "impressions": "15234",
      "clicks": "423",
      "spend": "312.45",
      "cpc": "0.739",
      "ctr": "2.776",
      "actions": [
        {"action_type": "link_click", "value": "423"},
        {"action_type": "landing_page_view", "value": "389"},
        {"action_type": "purchase", "value": "12", "1d_click": "8", "7d_click": "12"},
        {"action_type": "add_to_cart", "value": "45"}
      ],
      "date_start": "2026-07-01",
      "date_stop": "2026-07-01"
    },
    {
      "campaign_name": "Brand Awareness - Video",
      "campaign_id": "camp_002",
      "impressions": "82451",
      "clicks": "1205",
      "spend": "524.80",
      "cpc": "0.436",
      "ctr": "1.461",
      "actions": [
        {"action_type": "link_click", "value": "1205"},
        {"action_type": "video_view", "value": "18320"},
        {"action_type": "post_engagement", "value": "2450"}
      ],
      "date_start": "2026-07-01",
      "date_stop": "2026-07-01"
    }
  ],
  "paging": {
    "cursors": {
      "before": "MAZDZD",
      "after": "MjQZD"
    },
    "next": "https://graph.facebook.com/v25.0/act_123456/insights?access_token=EAA...&after=MjQZD"
  }
}
```

**Insights field values are always strings** (even numeric fields like `impressions`, `spend`, `clicks`).

### Common Insight Fields

| Field | Type | Description |
|-------|------|-------------|
| `impressions` | string | Number of impressions |
| `clicks` | string | Total clicks (all types) |
| `spend` | string | Amount spent (account currency) |
| `cpc` | string | Cost per click |
| `cpm` | string | Cost per 1000 impressions |
| `ctr` | string | Click-through rate (%) |
| `reach` | string | Unique accounts reached |
| `frequency` | string | Average times each person saw the ad |
| `actions` | array | Array of `{action_type, value}` objects |
| `cost_per_action_type` | array | Array of `{action_type, value}` objects |
| `date_start` | string | Period start (YYYY-MM-DD) |
| `date_stop` | string | Period end (YYYY-MM-DD) |

---

### 2. List Campaigns

```
GET /v25.0/{ad_account_id}/campaigns
```

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `access_token` | string | **required** | OAuth token |
| `fields` | string | — | `id,name,daily_budget,lifetime_budget,start_time,stop_time,status,budget_remaining` |
| `limit` | integer | 25 | Results per page (max 500) |
| `after` | string | — | Pagination cursor |

**Example request:**

```bash
curl "https://graph.facebook.com/v25.0/act_123456/campaigns?\
access_token=EAABsbCS1iHgBAxxxxxx&\
fields=id,name,daily_budget,lifetime_budget,start_time,stop_time,status,budget_remaining"
```

**Example response (200):**

```json
{
  "data": [
    {
      "id": "camp_001",
      "name": "Summer Sale - Prospecting",
      "daily_budget": "5000",
      "lifetime_budget": "0",
      "start_time": "2026-06-15T00:00:00-0700",
      "stop_time": "2026-08-31T23:59:59-0700",
      "status": "ACTIVE",
      "budget_remaining": "3200"
    },
    {
      "id": "camp_002",
      "name": "Brand Awareness - Video",
      "daily_budget": "8000",
      "lifetime_budget": "0",
      "start_time": "2026-07-01T00:00:00-0700",
      "status": "ACTIVE",
      "budget_remaining": "6500"
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

Budget values are in the **account currency's smallest unit** (cents for USD). `daily_budget: "5000"` = $50.00/day.

---

### 3. Ad Creative Details

```
GET /v25.0/{ad_id}
```

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `access_token` | string | **required** | OAuth token |
| `fields` | string | — | `preview_shareable_link,creative{id,name,title,body,image_url,thumbnail_url,object_story_spec}` |

**Example response (200):**

```json
{
  "id": "ad_001",
  "preview_shareable_link": "https://www.facebook.com/ads/archive/render_ad/?id=ad_001",
  "creative": {
    "id": "cr_001",
    "name": "Summer Sale Creative v2",
    "title": "50% Off Summer Collection",
    "body": "Limited time offer on our bestselling products. Shop now!",
    "image_url": "https://scontent.xx.fbcdn.net/v/t45.1600-4/...",
    "thumbnail_url": "https://scontent.xx.fbcdn.net/v/t45.1600-4/..."
  }
}
```

---

### 4. Ad Account Timezone

```
GET /v25.0/{ad_account_id}
```

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `access_token` | string | **required** | OAuth token |
| `fields` | string | — | `timezone_name` |

**Example response (200):**

```json
{
  "id": "act_123456",
  "timezone_name": "America/Los_Angeles"
}
```

---

## Pagination

Meta uses **cursor-based pagination** across all list endpoints.

### How it works

1. Make initial request
2. Check for `paging.next` — if present, there are more results
3. Extract `paging.cursors.after` and pass as `after` query parameter
4. Repeat until `paging.next` is absent or empty

### Rules

- `limit` max is **200** for insights, **500** for campaigns/ads
- `paging.next` is a full URL (including token) — but prefer extracting `cursors.after` and building the request yourself
- `paging.previous` exists for backward navigation
- When there are no more pages, `paging.next` is absent and `paging.cursors` may still be present

### Pseudocode

```python
results = []
after = None
while True:
    params = {"access_token": token, "fields": "impressions,clicks", "limit": 200}
    if after:
        params["after"] = after
    response = get(f"/v25.0/{account_id}/insights", params=params)
    results.extend(response["data"])
    paging = response.get("paging", {})
    if not paging.get("next"):
        break
    after = paging["cursors"]["after"]
```

---

## Date Chunking

For large date ranges, Meta may return errors (HTTP 500) or timeout. The dashboard-dbb client uses **7-day chunks**:

```python
CHUNK_DAYS = 7
# Split "2026-01-01 to 2026-06-30" into:
# 2026-01-01 to 2026-01-07
# 2026-01-08 to 2026-01-14
# ...etc
```

Each chunk is a separate API request with its own `time_range` parameter.

---

## Error Responses

### Missing Access Token

```json
{
  "error": {
    "message": "An active access token must be used to query information about the current user.",
    "type": "OAuthException",
    "code": 2500,
    "fbtrace_id": "AbCdEfGhIjKlMnOpQrSt"
  }
}
```

### Invalid Token

```json
{
  "error": {
    "message": "Invalid OAuth access token - Cannot parse access token",
    "type": "OAuthException",
    "code": 190,
    "fbtrace_id": "AbCdEfGhIjKlMnOpQrSt"
  }
}
```

### Rate Limit

```json
{
  "error": {
    "message": "(#80004) There have been too many calls to this ad-account. Wait a bit and try again.",
    "type": "OAuthException",
    "code": 80004,
    "error_subcode": 2446079,
    "fbtrace_id": "AbCdEfGhIjKlMnOpQrSt"
  }
}
```

---

## Notes

- All insight metric values are **strings**, not numbers (even `impressions`, `spend`, `clicks`)
- `actions` is an array of objects, each with `action_type` and `value`. Attribution windows (`1d_click`, `7d_click`) appear as additional keys on action objects when requested
- Budget values are in the account currency's smallest unit
- The `time_range` parameter must be a JSON string, not a query parameter object
- Retry on status codes 429, 500, 502, 503 with exponential backoff (1–4s, 3 attempts)
- Insights have a maximum of 200 results per page; campaigns/creatives allow up to 500

---

## Reference

- [Insights API](https://developers.facebook.com/docs/marketing-api/insights/) -- Overview of the Ads Insights API with usage examples
- [Ad Account Insights Reference](https://developers.facebook.com/docs/marketing-api/reference/ad-account/insights/) -- Full parameter and response field specification for account-level insights
- [Breakdowns](https://developers.facebook.com/docs/marketing-api/insights/breakdowns/) -- Complete list of available breakdown values
- [Limits and Best Practices](https://developers.facebook.com/docs/marketing-api/insights/best-practices/) -- Rate limiting, error codes, and optimization guidance
- [Graph API Versions](https://developers.facebook.com/docs/graph-api/changelog/versions/) -- Graph API version lifecycle and deprecation schedule
- [Introducing Graph API v25.0](https://developers.facebook.com/blog/post/2026/02/18/introducing-graph-api-v25-and-marketing-api-v25/) -- v25.0 release announcement
