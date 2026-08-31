# Google Ads REST API

## Overview

The Google Ads API provides access to campaigns, ad groups, keywords, creatives, geographic data, and performance metrics via GAQL (Google Ads Query Language). All queries go through a single streaming endpoint. Used by OS for search/display advertising data.

- **Category:** Search/Display Ads
- **Production Base URL:** `https://googleads.googleapis.com/v24`
- **Mock Base URL:** `http://localhost:8100/google-ads/v24`
- **API Version:** v24
- **Response Format:** JSON

## Authentication

Two headers are required on every request:

```
Authorization: Bearer {access_token}
developer-token: {developer_token}
Content-Type: application/json
```

For **manager (MCC) accounts** accessing client accounts, a third header is required:

```
login-customer-id: {manager_customer_id}
```

The `login-customer-id` value is the manager account's customer ID (without hyphens). This can be omitted when the OAuth credentials belong to the target client account directly.

### Token Refresh

Access tokens are obtained via OAuth 2.0 token refresh:

```
POST https://oauth2.googleapis.com/token
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token&
refresh_token={refresh_token}&
client_id={client_id}&
client_secret={client_secret}
```

**Example response (200):**

```json
{
  "access_token": "ya29.a0AfH6SMBx...",
  "expires_in": 3599,
  "scope": "https://www.googleapis.com/auth/adwords",
  "token_type": "Bearer"
}
```

### Mock Server

Any non-empty `Authorization: Bearer ...` and `developer-token: ...` headers are accepted. Returns 401 if either is missing.

---

## Endpoints

### 1. Search Stream (Primary Endpoint)

```
POST /v24/customers/{customer_id}/googleAds:searchStream
```

All data fetching goes through this single endpoint. The request body contains a GAQL query.

**Request body:**

```json
{
  "query": "SELECT campaign.name, metrics.clicks FROM campaign WHERE segments.date BETWEEN '2026-07-01' AND '2026-07-07'"
}
```

**Customer ID:** Numeric, dashes stripped (e.g., `1234567890` not `123-456-7890`).

---

### GAQL Query Examples

#### Campaign Performance

```sql
SELECT
  campaign.id,
  campaign.name,
  campaign.status,
  campaign.advertising_channel_type,
  campaign.bidding_strategy_type,
  ad_group.id,
  ad_group.name,
  ad_group.status,
  metrics.cost_micros,
  metrics.clicks,
  metrics.impressions,
  metrics.conversions,
  metrics.conversions_value,
  metrics.all_conversions,
  metrics.ctr,
  metrics.average_cpc,
  metrics.average_cpm,
  segments.date
FROM ad_group
WHERE segments.date BETWEEN '2026-07-01' AND '2026-07-07'
```

**Example response (200):**

```json
[
  {
    "results": [
      {
        "campaign": {
          "id": "camp_gads_001",
          "name": "Brand Search - Exact",
          "status": "ENABLED",
          "advertisingChannelType": "SEARCH",
          "biddingStrategyType": "TARGET_CPA"
        },
        "adGroup": {
          "id": "ag_001",
          "name": "Brand Terms",
          "status": "ENABLED"
        },
        "metrics": {
          "costMicros": "4523000000",
          "clicks": "1245",
          "impressions": "28340",
          "conversions": "89.0",
          "conversionsValue": "12450.50",
          "allConversions": "92.0",
          "ctr": "0.043935",
          "averageCpc": "3633735",
          "averageCpm": "159592370"
        },
        "segments": {
          "date": "2026-07-01"
        }
      },
      {
        "campaign": {
          "id": "camp_gads_002",
          "name": "Competitor Targeting",
          "status": "ENABLED",
          "advertisingChannelType": "SEARCH",
          "biddingStrategyType": "MAXIMIZE_CONVERSIONS"
        },
        "adGroup": {
          "id": "ag_002",
          "name": "Competitor Names",
          "status": "ENABLED"
        },
        "metrics": {
          "costMicros": "8920000000",
          "clicks": "2150",
          "impressions": "45200",
          "conversions": "42.0",
          "conversionsValue": "5880.00",
          "allConversions": "45.0",
          "ctr": "0.047566",
          "averageCpc": "4148837",
          "averageCpm": "197345132"
        },
        "segments": {
          "date": "2026-07-01"
        }
      }
    ]
  }
]
```

#### Device Breakdown

```sql
SELECT
  campaign.name,
  metrics.clicks,
  metrics.impressions,
  metrics.cost_micros,
  segments.device,
  segments.date
FROM ad_group
WHERE segments.date BETWEEN '2026-07-01' AND '2026-07-07'
```

**Example response (200):**

```json
[
  {
    "results": [
      {
        "campaign": {"name": "Brand Search - Exact"},
        "metrics": {"clicks": "823", "impressions": "18200", "costMicros": "2980000000"},
        "segments": {"device": "MOBILE", "date": "2026-07-01"}
      },
      {
        "campaign": {"name": "Brand Search - Exact"},
        "metrics": {"clicks": "422", "impressions": "10140", "costMicros": "1543000000"},
        "segments": {"device": "DESKTOP", "date": "2026-07-01"}
      }
    ]
  }
]
```

#### Keyword Quality Scores

```sql
SELECT
  ad_group.name,
  ad_group_criterion.keyword.text,
  ad_group_criterion.keyword.match_type,
  ad_group_criterion.quality_info.quality_score,
  ad_group_criterion.quality_info.creative_quality_score,
  ad_group_criterion.quality_info.post_click_quality_score,
  ad_group_criterion.quality_info.search_predicted_ctr,
  metrics.clicks,
  metrics.impressions,
  metrics.cost_micros,
  segments.date
FROM keyword_view
WHERE segments.date BETWEEN '2026-07-01' AND '2026-07-07'
```

**Example response (200):**

```json
[
  {
    "results": [
      {
        "adGroup": {"name": "Brand Terms"},
        "adGroupCriterion": {
          "keyword": {
            "text": "acme software",
            "matchType": "EXACT"
          },
          "qualityInfo": {
            "qualityScore": 9,
            "creativeQualityScore": "ABOVE_AVERAGE",
            "postClickQualityScore": "ABOVE_AVERAGE",
            "searchPredictedCtr": "ABOVE_AVERAGE"
          }
        },
        "metrics": {
          "clicks": "423",
          "impressions": "5200",
          "costMicros": "1520000000"
        },
        "segments": {"date": "2026-07-01"}
      }
    ]
  }
]
```

#### Geographic Performance

```sql
SELECT
  geographic_view.country_criterion_id,
  geographic_view.location_type,
  metrics.clicks,
  metrics.impressions,
  metrics.cost_micros,
  segments.date
FROM geographic_view
WHERE segments.date BETWEEN '2026-07-01' AND '2026-07-07'
```

**Example response (200):**

```json
[
  {
    "results": [
      {
        "geographicView": {
          "countryCriterionId": "2840",
          "locationType": "LOCATION_OF_PRESENCE"
        },
        "metrics": {"clicks": "2100", "impressions": "42000", "costMicros": "8500000000"},
        "segments": {"date": "2026-07-01"}
      },
      {
        "geographicView": {
          "countryCriterionId": "2826",
          "locationType": "LOCATION_OF_PRESENCE"
        },
        "metrics": {"clicks": "450", "impressions": "9800", "costMicros": "1800000000"},
        "segments": {"date": "2026-07-01"}
      }
    ]
  }
]
```

#### Campaign Budgets (no date filter)

```sql
SELECT
  campaign.id,
  campaign.name,
  campaign.status,
  campaign_budget.amount_micros,
  campaign_budget.type
FROM campaign
WHERE campaign.status != 'REMOVED'
```

**Example response (200):**

```json
[
  {
    "results": [
      {
        "campaign": {
          "id": "camp_gads_001",
          "name": "Brand Search - Exact",
          "status": "ENABLED"
        },
        "campaignBudget": {
          "amountMicros": "50000000",
          "type": "STANDARD"
        }
      }
    ]
  }
]
```

#### Search Terms

```sql
SELECT
  search_term_view.search_term,
  search_term_view.status,
  campaign.name,
  metrics.clicks,
  metrics.impressions,
  metrics.cost_micros,
  segments.date
FROM search_term_view
WHERE segments.date BETWEEN '2026-07-01' AND '2026-07-07'
```

---

## Pagination

**There is no pagination.** The `searchStream` endpoint returns all results in a single streaming response.

The response is an array that may contain one or more batch objects. Each batch contains a `results` array. The client handles both:

```python
data = response.json()
batches = data if isinstance(data, list) else [data]
all_results = []
for batch in batches:
    all_results.extend(batch["results"])
```

### Date Chunking

For large date ranges, the dashboard-dbb client splits requests into **7-day chunks** to manage response size:

```python
CHUNK_DAYS = 7
# "2026-01-01 to 2026-06-30" becomes:
# 2026-01-01 to 2026-01-07
# 2026-01-08 to 2026-01-14
# ...etc
```

---

## Monetary Values

All monetary values in Google Ads are in **micros** (divide by 1,000,000):

| Micros Value | Actual Value |
|-------------|-------------|
| `4523000000` | $4,523.00 |
| `3633735` | $3.63 (average CPC) |
| `50000000` | $50.00 (daily budget) |

---

## Error Responses

### 401 Unauthorized (missing headers)

```json
{
  "error": {
    "code": 401,
    "message": "Request is missing required authentication credential.",
    "status": "UNAUTHENTICATED"
  }
}
```

### 400 Bad Request (invalid GAQL)

```json
{
  "error": {
    "code": 400,
    "message": "Error in query: unexpected token 'FORM' at position 45",
    "status": "INVALID_ARGUMENT",
    "details": [
      {
        "errors": [
          {
            "errorCode": {"queryError": "UNEXPECTED_CLAUSE"},
            "message": "Error in query: unexpected token 'FORM' at position 45"
          }
        ]
      }
    ]
  }
}
```

### 429 Rate Limit

```json
{
  "error": {
    "code": 429,
    "message": "Resource has been exhausted (e.g. check quota).",
    "status": "RESOURCE_EXHAUSTED"
  }
}
```

---

## Notes

- All queries go through a single POST endpoint — there are no separate GET endpoints for different resources
- The response can be either a single batch object or an array of batch objects — always normalize to array
- GAQL uses SQL-like syntax but with Google Ads-specific resource names and field paths (dot notation)
- Metric field names in GAQL use `snake_case` (`cost_micros`) but response JSON uses `camelCase` (`costMicros`)
- `qualityScore` is an integer (1–10); quality score sub-components are enum strings: `BELOW_AVERAGE`, `AVERAGE`, `ABOVE_AVERAGE`
- Campaign status enum: `ENABLED`, `PAUSED`, `REMOVED`
- Device enum: `MOBILE`, `DESKTOP`, `TABLET`, `CONNECTED_TV`, `OTHER`
- Retry on HTTP 429, 500, 502, 503 with exponential backoff (1–4s, 3 attempts)
- Date chunking (7-day windows) is a client-side concern, not enforced by the API
- Google Ads API v24 is the newest major version available (latest release v24.2, June 2026); v23 and v22 are also currently supported

---

## Reference

- [Search and SearchStream](https://developers.google.com/google-ads/api/rest/common/search) -- searchStream endpoint specification, request/response format, comparison with paginated search
- [Authorization and HTTP Headers](https://developers.google.com/google-ads/api/rest/auth) -- Required headers (Authorization, developer-token, login-customer-id) and OAuth token refresh
- [REST Interface Design](https://developers.google.com/google-ads/api/rest/design/overview) -- REST API design overview and discovery document
- [REST API Examples](https://developers.google.com/google-ads/api/rest/examples) -- GAQL query examples with curl
- [SearchStream RPC Reference (v24)](https://developers.google.com/google-ads/api/reference/rpc/v24/GoogleAdsService/SearchStream) -- Detailed SearchStream method reference
- [API Release Notes](https://developers.google.com/google-ads/api/docs/release-notes) -- Version history, new features, and sunset schedule
