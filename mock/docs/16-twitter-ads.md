# X/Twitter Ads API

## Overview

The X (formerly Twitter) Ads API v12 provides programmatic access to manage ad accounts, campaigns, line items, promoted content, and analytics on the X platform.

> **Note:** The API has migrated from `ads-api.x.com` to `ads-api.x.com`. This doc uses the current domain.

## Base URL

```
https://ads-api.x.com/12/
```

## Authentication

OAuth 1.0a signed requests (not OAuth 2.0 Bearer tokens). Each request requires a new `Authorization` header signed with HMAC-SHA1.

```
Authorization: OAuth oauth_consumer_key="...", oauth_nonce="...", oauth_signature="...", oauth_signature_method="HMAC-SHA1", oauth_timestamp="...", oauth_token="...", oauth_version="1.0"
Content-Type: application/json
```

Returns 401 without a valid token:
```json
{
  "errors": [
    {
      "code": "UNAUTHORIZED_ACCESS",
      "message": "This request is not properly authenticated"
    }
  ],
  "request": {
    "params": {}
  }
}
```

## Rate Limits

Two-tier rate limiting:

1. **User token level** — global across all ad accounts per OAuth token
2. **Ad account level** — per account, GET requests only

Rate limit headers:
```
x-rate-limit-limit: 2000
x-rate-limit-remaining: 1984
x-rate-limit-reset: 1720500000

x-account-rate-limit-limit: 2000
x-account-rate-limit-remaining: 1998
x-account-rate-limit-reset: 1720500000
```

HTTP 429 when exceeded. Check `x-rate-limit-reset` (epoch time) for when the limit resets.

---

## Endpoints

### GET /12/accounts

Returns all ad accounts accessible to the authenticated user.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `count` | int | 200 | Max results per page (1-1000) |
| `cursor` | string | — | Pagination cursor |
| `sort_by` | string | — | Field to sort by |
| `with_deleted` | bool | false | Include deleted accounts |

**Example Request:**
```bash
curl -H "Authorization: OAuth oauth_consumer_key="...",oauth_token="..."" \
  "https://ads-api.x.com/12/accounts"
```

**Example Response:**
```json
{
  "data": [
    {
      "id": "twacct_acme_001",
      "name": "Acme Corp Ads",
      "business_name": "Acme Corp",
      "business_id": "twbiz_acme_001",
      "timezone": "US/Eastern",
      "timezone_switch_at": "2025-01-10T08:00:00Z",
      "country_code": "US",
      "currency": "USD",
      "created_at": "2025-01-10T08:00:00Z",
      "updated_at": "2026-07-01T12:00:00Z",
      "approval_status": "ACCEPTED",
      "deleted": false,
      "salt": "abc123def456",
      "industry_type": "TECHNOLOGY"
    },
    {
      "id": "twacct_globex_001",
      "name": "Globex Inc Advertising",
      "business_name": "Globex Inc",
      "business_id": "twbiz_globex_001",
      "timezone": "US/Pacific",
      "timezone_switch_at": "2025-03-15T09:00:00Z",
      "country_code": "US",
      "currency": "USD",
      "created_at": "2025-03-15T09:00:00Z",
      "updated_at": "2026-06-20T14:00:00Z",
      "approval_status": "ACCEPTED",
      "deleted": false,
      "salt": "ghi789jkl012",
      "industry_type": "RETAIL"
    }
  ],
  "total_count": 2,
  "request": {
    "params": {
      "account_ids": [],
      "count": 200,
      "cursor": null,
      "sort_by": ["created_at-desc"],
      "with_deleted": false
    }
  }
}
```

---

### GET /12/accounts/{account_id}/campaigns

Returns campaigns for an ad account.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `count` | int | 200 | Max results per page |
| `cursor` | string | — | Pagination cursor |
| `campaign_ids` | string | — | Comma-separated campaign IDs to filter |
| `with_deleted` | bool | false | Include deleted campaigns |
| `with_draft` | bool | false | Include draft campaigns |
| `funding_instrument_ids` | string | — | Filter by funding instrument |

**Example Request:**
```bash
curl -H "Authorization: OAuth oauth_consumer_key="...",oauth_token="..."" \
  "https://ads-api.x.com/12/accounts/twacct_acme_001/campaigns"
```

**Example Response:**
```json
{
  "data": [
    {
      "id": "twcamp_acme_brand_001",
      "name": "Acme Brand Awareness Summer 2026",
      "account_id": "twacct_acme_001",
      "funding_instrument_id": "twfi_acme_001",
      "entity_status": "ACTIVE",
      "servable": true,
      "start_time": "2026-07-01T00:00:00Z",
      "end_time": "2026-09-30T23:59:59Z",
      "daily_budget_amount_local_micro": 5000000000,
      "total_budget_amount_local_micro": 450000000000,
      "currency": "USD",
      "standard_delivery": true,
      "frequency_cap": 3,
      "duration_in_days": 7,
      "purchase_order_number": null,
      "created_at": "2026-06-25T10:00:00Z",
      "updated_at": "2026-07-10T09:00:00Z",
      "deleted": false
    },
    {
      "id": "twcamp_acme_conv_001",
      "name": "Acme Product Launch Q3",
      "account_id": "twacct_acme_001",
      "funding_instrument_id": "twfi_acme_001",
      "entity_status": "ACTIVE",
      "servable": true,
      "start_time": "2026-07-15T00:00:00Z",
      "end_time": null,
      "daily_budget_amount_local_micro": 2500000000,
      "total_budget_amount_local_micro": null,
      "currency": "USD",
      "standard_delivery": true,
      "frequency_cap": null,
      "duration_in_days": null,
      "purchase_order_number": null,
      "created_at": "2026-07-10T14:00:00Z",
      "updated_at": "2026-07-10T14:00:00Z",
      "deleted": false
    }
  ],
  "total_count": 2,
  "next_cursor": null,
  "request": {
    "params": {
      "account_id": "twacct_acme_001",
      "count": 200,
      "cursor": null,
      "with_deleted": false,
      "with_draft": false
    }
  }
}
```

---

### GET /12/accounts/{account_id}/line_items

Returns line items (ad groups) for an ad account.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `count` | int | 200 | Max results per page |
| `cursor` | string | — | Pagination cursor |
| `campaign_ids` | string | — | Filter by campaign IDs |
| `line_item_ids` | string | — | Filter by specific line item IDs |
| `with_deleted` | bool | false | Include deleted line items |

**Example Request:**
```bash
curl -H "Authorization: OAuth oauth_consumer_key="...",oauth_token="..."" \
  "https://ads-api.x.com/12/accounts/twacct_acme_001/line_items?campaign_ids=twcamp_acme_brand_001"
```

**Example Response:**
```json
{
  "data": [
    {
      "id": "twli_acme_001",
      "name": "Acme - 18-34 Tech Interest",
      "campaign_id": "twcamp_acme_brand_001",
      "account_id": "twacct_acme_001",
      "entity_status": "ACTIVE",
      "servable": true,
      "objective": "REACH",
      "placements": ["ALL_ON_TWITTER"],
      "product_type": "PROMOTED_TWEETS",
      "bid_strategy": "AUTO",
      "bid_amount_local_micro": null,
      "charge_by": "IMPRESSION",
      "optimization": "DEFAULT",
      "advertiser_domain": "acme.io",
      "target_cpa_local_micro": null,
      "daily_budget_amount_local_micro": null,
      "total_budget_amount_local_micro": null,
      "start_time": "2026-07-01T00:00:00Z",
      "end_time": "2026-09-30T23:59:59Z",
      "audience_expansion": "NARROW",
      "tracking_tags": [],
      "pay_by": "IMPRESSION",
      "creative_source": "MANUAL",
      "automatically_select_bid": true,
      "created_at": "2026-06-25T10:30:00Z",
      "updated_at": "2026-07-10T09:00:00Z",
      "deleted": false
    }
  ],
  "total_count": 1,
  "next_cursor": null,
  "request": {
    "params": {
      "account_id": "twacct_acme_001",
      "campaign_ids": ["twcamp_acme_brand_001"],
      "count": 200,
      "cursor": null,
      "with_deleted": false
    }
  }
}
```

---

### GET /12/stats/accounts/{account_id}

Returns aggregated performance statistics for an ad account.

**Query Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `entity` | string | Yes | Entity type: `ACCOUNT`, `CAMPAIGN`, `FUNDING_INSTRUMENT`, `LINE_ITEM`, `PROMOTED_ACCOUNT`, `PROMOTED_TWEET` |
| `entity_ids` | string | Yes | Comma-separated entity IDs (max 20) |
| `start_time` | string | Yes | ISO 8601 start (inclusive) |
| `end_time` | string | Yes | ISO 8601 end (exclusive) |
| `granularity` | string | Yes | `TOTAL`, `DAY`, `HOUR` |
| `metric_groups` | string | Yes | Comma-separated: `ENGAGEMENT`, `BILLING`, `VIDEO`, `WEB_CONVERSION`, `MOBILE_CONVERSION`, `LIFE_TIME_VALUE_MOBILE_CONVERSION` |
| `placement` | string | Yes | `ALL_ON_TWITTER`, `SPOTLIGHT`, `TREND` |
| `segmentation_type` | string | No | `AGE`, `GENDER`, `METROS`, `PLATFORMS` (async only) |

**Example Request:**
```bash
curl -H "Authorization: OAuth oauth_consumer_key="...",oauth_token="..."" \
  "https://ads-api.x.com/12/stats/accounts/twacct_acme_001?entity=CAMPAIGN&entity_ids=twcamp_acme_brand_001&start_time=2026-07-01T00:00:00Z&end_time=2026-07-08T00:00:00Z&granularity=DAY&metric_groups=ENGAGEMENT,BILLING"
```

**Example Response:**
```json
{
  "data": [
    {
      "id": "twcamp_acme_brand_001",
      "id_data": [
        {
          "segment": null,
          "metrics": {
            "impressions": [145200, 152800, 148600, 155100, 142000, 160300, 158900],
            "engagements": [8200, 8900, 8500, 9100, 7800, 9400, 9200],
            "clicks": [3800, 4100, 3900, 4200, 3600, 4500, 4300],
            "likes": [2100, 2300, 2200, 2400, 2000, 2600, 2500],
            "retweets": [450, 480, 460, 510, 420, 530, 500],
            "replies": [120, 130, 125, 140, 110, 150, 140],
            "follows": [35, 42, 38, 45, 30, 48, 44],
            "url_clicks": [1800, 1950, 1850, 2000, 1700, 2100, 2050],
            "billed_engagements": [145200, 152800, 148600, 155100, 142000, 160300, 158900],
            "billed_charge_local_micro": [4250000000, 4500000000, 4350000000, 4600000000, 4100000000, 4750000000, 4680000000]
          }
        }
      ]
    }
  ],
  "data_type": "stats",
  "time_series_length": 7,
  "request": {
    "params": {
      "account_id": "twacct_acme_001",
      "entity": "CAMPAIGN",
      "entity_ids": ["twcamp_acme_brand_001"],
      "start_time": "2026-07-01T00:00:00Z",
      "end_time": "2026-07-08T00:00:00Z",
      "granularity": "DAY",
      "metric_groups": ["ENGAGEMENT", "BILLING"],
      "placement": "ALL_ON_TWITTER"
    }
  }
}
```

---

## Pagination

Cursor-based via `next_cursor` in the response.

```json
{
  "data": [...],
  "total_count": 150,
  "next_cursor": "8x7v6w5",
  "request": { "params": { "cursor": null, "count": 200 } }
}
```

- Pass `cursor` query parameter with the `next_cursor` value for next page
- Pass `count` to control page size (default 200, max 1000)
- When `next_cursor` is `null`, there are no more results
- `total_count` gives the total number of matching entities

## Error Responses

```json
{
  "errors": [
    {
      "code": "INVALID_PARAMETER",
      "message": "Expected Long for account_id, got 'invalid'",
      "parameter": "account_id"
    }
  ],
  "request": {
    "params": {
      "account_id": "invalid"
    }
  }
}
```

| HTTP Status | Code | Meaning |
|-------------|------|---------|
| 400 | INVALID_PARAMETER | Bad request / invalid parameter value |
| 401 | UNAUTHORIZED_ACCESS | Invalid or expired token |
| 403 | UNAUTHORIZED_CLIENT_APPLICATION | App not approved for Ads API |
| 404 | ROUTE_NOT_FOUND | Endpoint or resource not found |
| 429 | RATE_LIMIT | Rate limit exceeded |
| 500 | INTERNAL_ERROR | Server error |
| 503 | SERVICE_UNAVAILABLE | Temporary outage |

## Notes

- All monetary values are in **micro-currency** (divide by 1,000,000). E.g., `billed_charge_local_micro: 4250000000` = $4,250.00
- Stats metrics are returned as **arrays** (one value per time period matching the granularity)
- `time_series_length` in the stats response tells you how many time buckets are in each array
- `entity_status` values: `ACTIVE`, `PAUSED`, `DRAFT`
- `servable` indicates whether the entity is actually eligible to serve (can be false even if ACTIVE due to parent status, budget, etc.)
- The `request.params` echo in every response confirms what parameters were used
- Line item `objective` values: `APP_ENGAGEMENTS`, `APP_INSTALLS`, `REACH`, `FOLLOWERS`, `ENGAGEMENTS`, `VIDEO_VIEWS`, `PREROLL_VIEWS`, `WEBSITE_CLICKS`
- Line item `product_type` values: `PROMOTED_TWEETS`, `PROMOTED_ACCOUNTS`, `MEDIA`
- Line item `bid_strategy` values: `AUTO`, `TARGET`
- Synchronous stats endpoint: max 7-day range, rate limit 250 requests per 15 minutes
- Async stats available via `POST /12/stats/jobs/accounts/:account_id` (max 90-day range, 100 concurrent jobs)
- Stats data finalizes after 24 hours (spend data after 3 days)
- `null` values in metrics arrays indicate no data (not zero)

## Reference

- [X Ads API Introduction](https://docs.x.com/x-ads-api/introduction)
- [Making Authenticated Requests (OAuth 1.0a)](https://docs.x.com/x-ads-api/fundamentals/making-authenticated-requests)
- [Versioning](https://docs.x.com/x-ads-api/fundamentals/versioning)
- [Campaign Management](https://docs.x.com/x-ads-api/campaign-management)
- [Campaign Management API Reference](https://docs.x.com/x-ads-api/campaign-management/reference)
- [Analytics](https://docs.x.com/x-ads-api/analytics)
- [Hierarchy and Terminology](https://docs.x.com/x-ads-api/fundamentals/hierarchy-and-terminology)
