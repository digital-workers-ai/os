# Snapchat Marketing API

## Overview

Snapchat Marketing API v1 provides programmatic access to manage ad accounts, campaigns, ad squads, ads, creatives, and reporting within the Snapchat Ads platform.

## Base URL

```
https://adsapi.snapchat.com/v1/
```

## Authentication

OAuth 2.0 Bearer token.

```
Authorization: Bearer {access_token}
Content-Type: application/json
```

Access tokens are obtained via OAuth 2.0 authorization code flow:
- Authorization: `https://accounts.snapchat.com/login/oauth2/authorize`
- Token exchange: `https://accounts.snapchat.com/login/oauth2/access_token`

Returns 401 without a valid token:
```json
{
  "request_status": "ERROR",
  "request_id": "abc123",
  "debug_message": "Unauthorized",
  "display_message": "We're sorry, but the request could not be completed. Please try again.",
  "error_code": "E0001"
}
```

## Rate Limits

- **Application-level:** 20 requests/second (averaged)
- **Access-token-level:** 10 requests/second (averaged)
- HTTP 429 on exceeded

---

## Endpoints

### GET /v1/me/organizations

Returns all organizations the authenticated user belongs to.

**Example Request:**
```bash
curl -H "Authorization: Bearer snap_mock_token_123" \
  https://adsapi.snapchat.com/v1/me/organizations
```

**Example Response:**
```json
{
  "request_status": "SUCCESS",
  "request_id": "63a1b2c3d4e5f6",
  "organizations": [
    {
      "sub_request_status": "SUCCESS",
      "organization": {
        "id": "org_acme_001",
        "updated_at": "2026-06-15T10:30:00.000Z",
        "created_at": "2025-01-10T08:00:00.000Z",
        "name": "Acme Corp Marketing",
        "country": "US",
        "currency": "USD",
        "type": "ENTERPRISE",
        "state": "ACTIVE",
        "roles": ["admin"],
        "my_display_name": "Jane Smith",
        "my_invited_email": "jane@acme.io",
        "my_member_id": "mem_jane_001"
      }
    },
    {
      "sub_request_status": "SUCCESS",
      "organization": {
        "id": "org_globex_001",
        "updated_at": "2026-05-20T14:00:00.000Z",
        "created_at": "2025-03-15T09:00:00.000Z",
        "name": "Globex Inc",
        "country": "US",
        "currency": "USD",
        "type": "ENTERPRISE",
        "state": "ACTIVE",
        "roles": ["member"],
        "my_display_name": "Jane Smith",
        "my_invited_email": "jane@globex.com",
        "my_member_id": "mem_jane_002"
      }
    }
  ]
}
```

---

### GET /v1/organizations/{organization_id}/adaccounts

Returns all ad accounts under an organization.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 1000 | Max results per page (50-1000) |
| `cursor` | string | — | Pagination cursor from previous response |

**Example Request:**
```bash
curl -H "Authorization: Bearer snap_mock_token_123" \
  "https://adsapi.snapchat.com/v1/organizations/org_acme_001/adaccounts?limit=10"
```

**Example Response:**
```json
{
  "request_status": "SUCCESS",
  "request_id": "74b2c3d4e5f6a7",
  "adaccounts": [
    {
      "sub_request_status": "SUCCESS",
      "adaccount": {
        "id": "adacct_acme_001",
        "updated_at": "2026-07-01T12:00:00.000Z",
        "created_at": "2025-02-01T10:00:00.000Z",
        "name": "Acme Corp - US",
        "type": "PARTNER",
        "status": "ACTIVE",
        "organization_id": "org_acme_001",
        "currency": "USD",
        "timezone": "America/New_York",
        "advertiser": "Acme Corp",
        "advertiser_organization_id": "org_acme_001",
        "billing_type": "IO",
        "lifetime_spend_cap_micro": 500000000000,
        "regulations": {
          "restricted_delivery_signals": false
        }
      }
    }
  ],
  "paging": {
    "next_link": "https://adsapi.snapchat.com/v1/organizations/org_acme_001/adaccounts?cursor=eyJsYXN0X2lkIjoiYWRh&limit=10"
  }
}
```

---

### GET /v1/adaccounts/{ad_account_id}/campaigns

Returns campaigns for an ad account.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 50 | Max results per page |
| `cursor` | string | — | Pagination cursor |

**Example Request:**
```bash
curl -H "Authorization: Bearer snap_mock_token_123" \
  "https://adsapi.snapchat.com/v1/adaccounts/adacct_acme_001/campaigns"
```

**Example Response:**
```json
{
  "request_status": "SUCCESS",
  "request_id": "85c3d4e5f6a7b8",
  "campaigns": [
    {
      "sub_request_status": "SUCCESS",
      "campaign": {
        "id": "camp_acme_brand_001",
        "updated_at": "2026-07-10T09:00:00.000Z",
        "created_at": "2026-01-15T08:00:00.000Z",
        "name": "Acme Brand Awareness Q3",
        "ad_account_id": "adacct_acme_001",
        "status": "ACTIVE",
        "objective": "BRAND_AWARENESS",
        "start_time": "2026-07-01T00:00:00.000Z",
        "end_time": "2026-09-30T23:59:59.000Z",
        "daily_budget_micro": 5000000000,
        "lifetime_spend_cap_micro": 450000000000,
        "measurement_spec": {
          "ios_14_campaign_tracking_enabled": true
        }
      }
    },
    {
      "sub_request_status": "SUCCESS",
      "campaign": {
        "id": "camp_acme_conv_001",
        "updated_at": "2026-07-08T14:30:00.000Z",
        "created_at": "2026-03-01T10:00:00.000Z",
        "name": "Acme Product Launch - Conversions",
        "ad_account_id": "adacct_acme_001",
        "status": "ACTIVE",
        "objective": "WEB_CONVERSIONS",
        "start_time": "2026-03-01T00:00:00.000Z",
        "end_time": null,
        "daily_budget_micro": 2500000000,
        "lifetime_spend_cap_micro": null,
        "measurement_spec": {
          "ios_14_campaign_tracking_enabled": true
        }
      }
    }
  ],
  "paging": {}
}
```

---

### GET /v1/adaccounts/{ad_account_id}/adsquads

Returns ad squads (ad sets) for an ad account.

**Example Request:**
```bash
curl -H "Authorization: Bearer snap_mock_token_123" \
  "https://adsapi.snapchat.com/v1/adaccounts/adacct_acme_001/adsquads"
```

**Example Response:**
```json
{
  "request_status": "SUCCESS",
  "request_id": "96d4e5f6a7b8c9",
  "adsquads": [
    {
      "sub_request_status": "SUCCESS",
      "adsquad": {
        "id": "adsq_acme_001",
        "updated_at": "2026-07-10T09:00:00.000Z",
        "created_at": "2026-01-15T08:30:00.000Z",
        "name": "Acme 18-35 Interest Targeting",
        "campaign_id": "camp_acme_brand_001",
        "status": "ACTIVE",
        "type": "SNAP_ADS",
        "placement_v2": {
          "config": "AUTOMATIC"
        },
        "billing_event": "IMPRESSION",
        "auto_bid": true,
        "bid_strategy": "AUTO_BID",
        "daily_budget_micro": 2500000000,
        "start_time": "2026-07-01T00:00:00.000Z",
        "end_time": "2026-09-30T23:59:59.000Z",
        "optimization_goal": "IMPRESSIONS",
        "targeting": {
          "geos": [
            {"country_code": "us"}
          ],
          "demographics": [
            {"age_groups": ["18-20", "21-24", "25-34"]}
          ],
          "interests": [
            {"category_id": "SLC_123", "name": "Technology"}
          ]
        },
        "reach_and_frequency_status": "UNCAPPED"
      }
    }
  ],
  "paging": {}
}
```

---

### GET /v1/adaccounts/{ad_account_id}/ads

Returns ads within an ad account.

**Example Request:**
```bash
curl -H "Authorization: Bearer snap_mock_token_123" \
  "https://adsapi.snapchat.com/v1/adaccounts/adacct_acme_001/ads"
```

**Example Response:**
```json
{
  "request_status": "SUCCESS",
  "request_id": "a7e5f6a7b8c9d0",
  "ads": [
    {
      "sub_request_status": "SUCCESS",
      "ad": {
        "id": "ad_acme_001",
        "updated_at": "2026-07-10T09:15:00.000Z",
        "created_at": "2026-01-16T11:00:00.000Z",
        "name": "Acme Hero Video - Summer 2026",
        "ad_squad_id": "adsq_acme_001",
        "creative_id": "cre_acme_001",
        "status": "ACTIVE",
        "type": "SNAP_AD",
        "review_status": "APPROVED",
        "review_status_reasons": [],
        "paying_advertiser_name": "Acme Corp"
      }
    },
    {
      "sub_request_status": "SUCCESS",
      "ad": {
        "id": "ad_acme_002",
        "updated_at": "2026-07-08T16:00:00.000Z",
        "created_at": "2026-03-02T09:00:00.000Z",
        "name": "Acme Product Demo - Carousel",
        "ad_squad_id": "adsq_acme_001",
        "creative_id": "cre_acme_002",
        "status": "ACTIVE",
        "type": "SNAP_AD",
        "review_status": "APPROVED",
        "review_status_reasons": [],
        "paying_advertiser_name": "Acme Corp"
      }
    }
  ],
  "paging": {}
}
```

---

### GET /v1/adaccounts/{ad_account_id}/stats

Returns performance statistics for an ad account.

**Query Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `granularity` | string | Yes | `TOTAL`, `DAY`, `HOUR`, `LIFETIME` |
| `start_time` | string | Yes | ISO 8601 start |
| `end_time` | string | Yes | ISO 8601 end |
| `fields` | string | No | Comma-separated stat fields |
| `breakdown` | string | No | Entity-level: `ad`, `adsquad`. For dimensions use `report_dimension`: `GEO`, `DEMO`, `INTEREST`, `DEVICE` |

**Example Request:**
```bash
curl -H "Authorization: Bearer snap_mock_token_123" \
  "https://adsapi.snapchat.com/v1/adaccounts/adacct_acme_001/stats?granularity=DAY&start_time=2026-07-01T00:00:00.000Z&end_time=2026-07-08T00:00:00.000Z"
```

**Example Response:**
```json
{
  "request_status": "SUCCESS",
  "request_id": "b8f6a7b8c9d0e1",
  "timeseries_stats": [
    {
      "sub_request_status": "SUCCESS",
      "timeseries_stat": {
        "id": "adacct_acme_001",
        "type": "AD_ACCOUNT",
        "granularity": "DAY",
        "start_time": "2026-07-01T00:00:00.000Z",
        "end_time": "2026-07-08T00:00:00.000Z",
        "finalized_data_end_time": "2026-07-06T00:00:00.000Z",
        "timeseries": [
          {
            "start_time": "2026-07-01T00:00:00.000Z",
            "end_time": "2026-07-02T00:00:00.000Z",
            "stats": {
              "impressions": 145200,
              "swipes": 3800,
              "spend": 4250000000,
              "video_views": 98000,
              "video_views_time_based": 72000,
              "video_views_15s": 45000,
              "screen_time_millis": 892000000,
              "quartile_1": 120000,
              "quartile_2": 95000,
              "quartile_3": 72000,
              "view_completion": 48000,
              "frequency": 2.3,
              "uniques": 63130
            }
          },
          {
            "start_time": "2026-07-02T00:00:00.000Z",
            "end_time": "2026-07-03T00:00:00.000Z",
            "stats": {
              "impressions": 152800,
              "swipes": 4100,
              "spend": 4500000000,
              "video_views": 103000,
              "video_views_time_based": 76000,
              "video_views_15s": 48000,
              "screen_time_millis": 945000000,
              "quartile_1": 126000,
              "quartile_2": 100000,
              "quartile_3": 76000,
              "view_completion": 51000,
              "frequency": 2.4,
              "uniques": 63667
            }
          }
        ]
      }
    }
  ]
}
```

---

## Pagination

Cursor-based. Responses include a `paging` object when more results are available.

```json
{
  "paging": {
    "next_link": "https://adsapi.snapchat.com/v1/...?cursor=eyJsYXN0...&limit=50"
  }
}
```

- Follow the `next_link` URL to fetch the next page
- Pass `limit` to control page size (default 1000, range 50-1000 for CRUD endpoints; max 200 for stats)
- Paginated results are ordered by `created_at`
- When `paging` is empty (`{}`) or absent, there are no more results

## Error Responses

All errors follow the same envelope:

```json
{
  "request_status": "ERROR",
  "request_id": "abc123def456",
  "debug_message": "Resource not found",
  "display_message": "We're sorry, but the request could not be completed.",
  "error_code": "E0007"
}
```

| HTTP Status | Error Code | Meaning |
|-------------|-----------|---------|
| 400 | E0003 | Bad request / invalid parameters |
| 401 | E0001 | Unauthorized — invalid or expired token |
| 403 | E0005 | Forbidden — insufficient permissions |
| 404 | E0007 | Resource not found |
| 429 | E0009 | Rate limit exceeded |
| 500 | E0000 | Internal server error |

## Notes

- All monetary values are in **micro-currency** (divide by 1,000,000). E.g., `spend: 4250000000` = $4,250.00
- Timestamps are ISO 8601 with milliseconds and `Z` suffix
- The `sub_request_status` field appears on each item in list responses
- Entity hierarchy: Organization → Ad Account → Campaign → Ad Squad → Ad + Creative
- Stats can be requested at campaign, ad squad, or ad level too (same endpoint pattern)
- `type` field on ads: `SNAP_AD`, `APP_INSTALL`, `REMOTE_WEBPAGE`, `DEEP_LINK`, `STORY`, `AD_TO_LENS`, `AD_TO_CALL`, `AD_TO_MESSAGE`, `FILTER`, `LENS`, `LENS_WEB_VIEW`, `LENS_APP_INSTALL`, `LENS_DEEP_LINK`, `COLLECTION`, `LEAD_GENERATION`, `REMINDER`
- Campaign `objective` values (legacy): `BRAND_AWARENESS`, `WEB_CONVERSIONS`, `APP_INSTALLS`, `VIDEO_VIEWS`, `LEAD_GENERATION`, `REACH`, `ENGAGEMENT`, `CATALOG_SALES`
- Campaign `objective_v2_type` values (current): `AWARENESS_AND_ENGAGEMENT`, `SALES`, `TRAFFIC`, `APP_PROMOTION`, `LEADS`
- Ad `review_status` values: `PENDING`, `APPROVED`, `REJECTED`
- Ad account `type` values: `DIRECT`, `PARTNER`
- Ad account `billing_type` values: `IO`, `REVOLVING`

## Reference

- [Snapchat Marketing API Home](https://developers.snap.com/marketing-api/home)
- [Authentication](https://developers.snap.com/marketing-api/Ads-API/authentication)
- [Ad Accounts](https://developers.snap.com/marketing-api/Ads-API/ad-accounts)
- [Campaigns](https://developers.snap.com/marketing-api/Ads-API/campaigns)
- [Ads](https://developers.snap.com/marketing-api/Ads-API/ads)
- [User](https://developers.snap.com/marketing-api/Ads-API/user)
- [Measurement / Stats](https://developers.snap.com/api/marketing-api/Ads-API/measurement)
- [Rate Limits](https://developers.snap.com/api/marketing-api/Ads-API/rate-limits)
- [API Patterns (Pagination, Errors)](https://developers.snap.com/api/marketing-api/Ads-API/api-patterns)
