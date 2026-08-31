# Pinterest Ads API v5

## Overview

Pinterest API for managing ad accounts, campaigns, ad groups, and ads. Also covers organic content (pins, boards). Uses bookmark-based cursor pagination. Currently at spec version 5.28.0.

## Base URL

```
https://api.pinterest.com/v5
```

Mock server prefix: `/pinterest/v5`

## Authentication

OAuth 2.0 Bearer token. Two auth schemes available:
- `pinterest_oauth2` — authorization code flow with scopes
- `client_credentials` — for server-to-server

```
Authorization: Bearer {access_token}
Content-Type: application/json
```

## Endpoints

### GET /ad_accounts

List ad accounts for the authenticated user.

**Query parameters:**
- `page_size` — items per page (default 25, min 1, max 250)
- `bookmark` — cursor for pagination (null or absent on first request)
- `include_shared_accounts` — boolean (default true)

**Example request:**

```
GET /pinterest/v5/ad_accounts?page_size=25
```

**Response:**

```json
{
  "items": [
    {
      "id": "549764905678",
      "name": "Acme Corp",
      "owner": {
        "username": "acmecorp"
      },
      "country": "US",
      "currency": "USD",
      "status": "ACTIVE",
      "created_time": 1710500000,
      "updated_time": 1720000000,
      "permissions": ["ADMIN", "ANALYST", "CAMPAIGN_MANAGER"]
    },
    {
      "id": "549764905679",
      "name": "Globex Marketing",
      "owner": {
        "username": "globex"
      },
      "country": "US",
      "currency": "USD",
      "status": "ACTIVE",
      "created_time": 1715000000,
      "updated_time": 1720500000,
      "permissions": ["ADMIN"]
    }
  ],
  "bookmark": null
}
```

### GET /ad_accounts/{ad_account_id}/campaigns

List campaigns for an ad account.

**Query parameters:**
- `page_size` — items per page (default 25, max 250)
- `bookmark` — cursor for pagination
- `entity_statuses` — filter by status (comma-separated: `ACTIVE`, `PAUSED`, `ARCHIVED`)
- `order` — `ASCENDING` or `DESCENDING`

**Example request:**

```
GET /pinterest/v5/ad_accounts/549764905678/campaigns?page_size=25&entity_statuses=ACTIVE,PAUSED
```

**Response:**

```json
{
  "items": [
    {
      "id": "626735565678",
      "ad_account_id": "549764905678",
      "name": "Summer Collection 2026",
      "status": "ACTIVE",
      "lifetime_spend_cap": 1500000,
      "daily_spend_cap": 50000,
      "objective_type": "AWARENESS",
      "created_time": 1719792000,
      "updated_time": 1720500000,
      "type": "campaign",
      "start_time": 1719792000,
      "end_time": 1727654400,
      "summary_status": "RUNNING",
      "is_flexible_daily_budgets": false,
      "default_ad_group_budget_in_micro_currency": null,
      "is_campaign_budget_optimization": true
    },
    {
      "id": "626735565679",
      "ad_account_id": "549764905678",
      "name": "Holiday Pins - Q4",
      "status": "PAUSED",
      "lifetime_spend_cap": 800000,
      "daily_spend_cap": null,
      "objective_type": "CONSIDERATION",
      "created_time": 1717200000,
      "updated_time": 1719000000,
      "type": "campaign",
      "start_time": 1730419200,
      "end_time": 1735689600,
      "summary_status": "NOT_STARTED",
      "is_flexible_daily_budgets": false,
      "default_ad_group_budget_in_micro_currency": null,
      "is_campaign_budget_optimization": false
    }
  ],
  "bookmark": "bk_c2FtcGxlX2Jvb2ttYXJr"
}
```

### GET /ad_accounts/{ad_account_id}/ad_groups

List ad groups.

**Query parameters:**
- `page_size`, `bookmark` — pagination
- `campaign_ids` — filter by campaign (comma-separated)
- `entity_statuses` — filter by status

**Response:**

```json
{
  "items": [
    {
      "id": "2680060704746",
      "ad_account_id": "549764905678",
      "campaign_id": "626735565678",
      "name": "Women 25-44 Interest",
      "status": "ACTIVE",
      "budget_in_micro_currency": 2000000,
      "budget_type": "DAILY",
      "bid_in_micro_currency": 150000,
      "bid_strategy_type": "AUTOMATIC_BID",
      "start_time": 1719792000,
      "end_time": 1727654400,
      "targeting_spec": {
        "GENDER": ["female"],
        "AGE_BUCKET": ["25-34", "35-44"],
        "INTEREST": ["fashion", "home_decor"],
        "LOCALE": ["en-US"]
      },
      "optimization_goal_metadata": {
        "conversion_tag_v3_goal_metadata": null,
        "frequency_goal_metadata": null
      },
      "placement_group": "ALL",
      "pacing_delivery_type": "STANDARD",
      "summary_status": "RUNNING",
      "created_time": 1719792000,
      "updated_time": 1720500000,
      "type": "adgroup"
    }
  ],
  "bookmark": null
}
```

### GET /ad_accounts/{ad_account_id}/ads

List ads.

**Query parameters:**
- `page_size`, `bookmark` — pagination
- `campaign_ids` — filter by campaign
- `ad_group_ids` — filter by ad group
- `entity_statuses` — filter by status

**Example request:**

```
GET /pinterest/v5/ad_accounts/549764905678/ads?page_size=25&campaign_ids=626735565678
```

**Response:**

```json
{
  "items": [
    {
      "id": "687201361234",
      "ad_account_id": "549764905678",
      "ad_group_id": "2680060704746",
      "campaign_id": "626735565678",
      "name": "Summer Dress - Lifestyle Shot",
      "status": "ACTIVE",
      "creative_type": "REGULAR",
      "pin_id": "1055231234567",
      "tracking_urls": {
        "impression": ["https://track.acme.io/imp?ad=687201361234"],
        "click": ["https://track.acme.io/click?ad=687201361234"]
      },
      "review_status": "APPROVED",
      "rejection_labels": [],
      "summary_status": "RUNNING",
      "click_tracking_url": "https://acme.io/summer?ref=pinterest",
      "view_tracking_url": null,
      "created_time": 1719800000,
      "updated_time": 1720500000,
      "type": "ad"
    },
    {
      "id": "687201361235",
      "ad_account_id": "549764905678",
      "ad_group_id": "2680060704746",
      "campaign_id": "626735565678",
      "name": "Summer Dress - Flat Lay",
      "status": "ACTIVE",
      "creative_type": "REGULAR",
      "pin_id": "1055231234568",
      "tracking_urls": null,
      "review_status": "APPROVED",
      "rejection_labels": [],
      "summary_status": "RUNNING",
      "click_tracking_url": "https://acme.io/summer?ref=pinterest&v=2",
      "view_tracking_url": null,
      "created_time": 1719800500,
      "updated_time": 1720500000,
      "type": "ad"
    }
  ],
  "bookmark": null
}
```

### GET /ad_accounts/{ad_account_id}/analytics

Get ad account analytics.

**Query parameters:**
- `start_date` (required) — `YYYY-MM-DD`
- `end_date` (required) — `YYYY-MM-DD`
- `columns` (required) — comma-separated metric names (e.g., `IMPRESSION,CLICKTHROUGH,SPEND_IN_MICRO_DOLLAR,CTR`)
- `granularity` — `DAY`, `HOUR`, `WEEK`, `MONTH`, `TOTAL`
- `click_window_days` — attribution window (default 30; valid: 1, 7, 14, 30)
- `view_window_days` — view attribution (default 1; valid: 1, 7, 14, 30)
- `engagement_window_days` — engagement attribution (default 30; valid: 1, 7, 14, 30)
- `conversion_report_time` — `TIME_OF_AD_ACTION` (default) or `TIME_OF_CONVERSION`

**Date range restrictions:**
- Non-HOUR granularity: up to 90 days back, max 90-day range
- HOUR granularity: up to 8 days back, max 3-day range

**Response:**

```json
[
  {
    "DATE": "2026-06-01",
    "IMPRESSION": 45000,
    "CLICKTHROUGH": 620,
    "SPEND_IN_MICRO_DOLLAR": 125000000,
    "CTR": 0.01378
  },
  {
    "DATE": "2026-06-02",
    "IMPRESSION": 42000,
    "CLICKTHROUGH": 580,
    "SPEND_IN_MICRO_DOLLAR": 118000000,
    "CTR": 0.01381
  }
]
```

Note: `SPEND_IN_MICRO_DOLLAR` is in micro-dollars (divide by 1,000,000). Analytics response is a flat array (not wrapped in `items`).

## Pagination

- **Mechanism:** Bookmark-based cursor
- **Page size:** `page_size` query parameter (default 25, min 1, max 250)
- **To get next page:** Pass `bookmark={value}` from previous response
- **Done when:** `bookmark` is `null` in the response

```
Page 1: GET /ad_accounts/549764905678/campaigns?page_size=25
         → bookmark: "bk_c2FtcGxlX2Jvb2ttYXJr"
Page 2: GET /ad_accounts/549764905678/campaigns?page_size=25&bookmark=bk_c2FtcGxlX2Jvb2ttYXJr
         → bookmark: "bk_bmV4dF9wYWdl"
Page 3: GET /ad_accounts/549764905678/campaigns?page_size=25&bookmark=bk_bmV4dF9wYWdl
         → bookmark: null  (done)
```

## Rate Limits

Per-operation rate limit categories (12 categories):
- `ads_read`, `ads_write`, `ads_analytics`
- `organic_read`, `organic_write`
- etc.

Rate limit info in response headers:
- `x-ratelimit-category`
- `x-ratelimit-limit`
- `x-ratelimit-remaining`
- `x-ratelimit-reset`

HTTP 429 on exceeded.

## Error Responses

**401 Unauthorized:**
```json
{
  "code": 1,
  "message": "Authentication failed. Please check your access token."
}
```

**403 Forbidden:**
```json
{
  "code": 29,
  "message": "You are not permitted to access this ad account."
}
```

**404 Not found:**
```json
{
  "code": 404,
  "message": "Campaign not found."
}
```

**429 Rate limited:**
```json
{
  "code": 8,
  "message": "Rate limit exceeded. Please retry later."
}
```

## Notes

- Budget/spend values in `_in_micro_currency` or `_in_micro_dollar` fields are in micro-units (divide by 1,000,000)
- Other budget fields like `lifetime_spend_cap` and `daily_spend_cap` are in the account's currency micro-units
- Analytics endpoint returns a flat array, not the `{items, bookmark}` envelope
- Timestamps are unix seconds (not milliseconds)
- Entity status enum: `ACTIVE`, `PAUSED`, `ARCHIVED`
- `summary_status` provides a computed status: `RUNNING`, `NOT_STARTED`, `PAUSED`, `COMPLETED`, etc.
- OpenAPI spec available at `github.com/pinterest/api-description`
- `creative_type` values: `REGULAR`, `VIDEO`, `SHOPPING`, `CAROUSEL`, `COLLECTION`, `IDEA`

## Reference

- [Get ad account analytics](https://developers.pinterest.com/docs/api/v5/ad_account-analytics/) -- Analytics endpoint parameters and response
- [List ad accounts](https://developers.pinterest.com/docs/api/v5/ad_accounts-list/) -- List ad accounts endpoint
- [Get campaign analytics](https://developers.pinterest.com/docs/api/v5/campaigns-analytics/) -- Campaign-level analytics
- [Pinterest API v5 Overview](https://developers.pinterest.com/docs/api/v5/) -- API reference index
- [OpenAPI spec (GitHub)](https://github.com/pinterest/api-description) -- Machine-readable API description (source of truth for parameter names and types)
- [Python SDK - AdsApi](https://github.com/pinterest/pinterest-python-generated-api-client/blob/main/docs/AdsApi.md) -- Auto-generated Python client docs with parameter details
