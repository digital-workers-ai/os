# LinkedIn Marketing API

## Overview

LinkedIn Marketing API for campaign management, ad analytics, and audience targeting. Uses versioned REST endpoints with a required version header. Part of the Microsoft ecosystem.

## Base URL

```
https://api.linkedin.com/rest/
```

Mock server prefix: `/linkedin/rest`

## Authentication

OAuth 2.0 Bearer token with required version header.

```
Authorization: Bearer {access_token}
Linkedin-Version: 202601
X-Restli-Protocol-Version: 2.0.0
Content-Type: application/json
```

The `X-Restli-Protocol-Version: 2.0.0` header is required for most REST calls.

**Version header:** `Linkedin-Version` is mandatory. Format is `YYYYMM` (e.g., `202601` for January 2026). Monthly versions, each supported for minimum 1 year.

**Token endpoint:** `https://www.linkedin.com/oauth/v2/accessToken`  
**Authorization URL:** `https://www.linkedin.com/oauth/v2/authorization`  
**Access tokens last:** 60 days (5,184,000 seconds)

**OAuth flow:** Three-legged authorization code flow.

## Endpoints

### GET /adAccounts

List ad accounts for the authenticated user.

**Query parameters:**
- `q` — search type (e.g., `search`)
- `search.status.values[0]` — filter by status (`ACTIVE`, `CANCELED`, `DRAFT`, `PENDING_DELETION`, `REMOVED`)
- `pageSize` — items per page (max 1,000). Cursor-based pagination from version 202401+.
- `pageToken` — cursor token from `metadata.nextPageToken` in previous response

**Example request:**

```
GET /linkedin/rest/adAccounts?q=search&search.status.values[0]=ACTIVE&pageSize=10
```

**Response:**

```json
{
  "elements": [
    {
      "id": 512345678,
      "name": "Acme Corp - Marketing",
      "status": "ACTIVE",
      "type": "BUSINESS",
      "currency": "USD",
      "reference": "urn:li:organization:12345",
      "servingStatuses": ["RUNNABLE"],
      "totalBudget": {
        "amount": "50000.00",
        "currencyCode": "USD"
      },
      "created": 1710500000000,
      "lastModified": 1720000000000
    },
    {
      "id": 512345679,
      "name": "Globex Inc - Lead Gen",
      "status": "ACTIVE",
      "type": "BUSINESS",
      "currency": "USD",
      "reference": "urn:li:organization:67890",
      "servingStatuses": ["RUNNABLE"],
      "totalBudget": {
        "amount": "25000.00",
        "currencyCode": "USD"
      },
      "created": 1715000000000,
      "lastModified": 1720500000000
    }
  ],
  "metadata": {
    "nextPageToken": "DgGerr1iVQreCJVjZDOW_grcp63nueBDipsS4DJpvJo"
  }
}
```

### GET /adAccounts/{adAccountId}/adCampaigns

List ad campaigns for an ad account.

**Query parameters:**
- `q` — `search`
- `search.status.values[0]` — filter by status (`ACTIVE`, `PAUSED`, `ARCHIVED`, `COMPLETED`, `CANCELED`, `DRAFT`)
- `pageSize` — items per page (max 1,000). Cursor-based pagination.
- `pageToken` — cursor token from `metadata.nextPageToken` in previous response

**Example request:**

```
GET /linkedin/rest/adAccounts/512345678/adCampaigns?q=search&search.status.values[0]=ACTIVE&pageSize=100
```

**Response:**

```json
{
  "elements": [
    {
      "id": 612345001,
      "name": "Brand Awareness - Q3 2026",
      "account": "urn:li:sponsoredAccount:512345678",
      "status": "ACTIVE",
      "type": "SPONSORED_UPDATES",
      "costType": "CPM",
      "objectiveType": "BRAND_AWARENESS",
      "dailyBudget": {
        "amount": "200.00",
        "currencyCode": "USD"
      },
      "totalBudget": {
        "amount": "6000.00",
        "currencyCode": "USD"
      },
      "runSchedule": {
        "start": 1719792000000,
        "end": 1727654400000
      },
      "unitCost": {
        "amount": "12.50",
        "currencyCode": "USD"
      },
      "targeting": {
        "includedTargetingFacets": {
          "locations": ["urn:li:geo:103644278"],
          "interfaceLocales": [{"country": "US", "language": "en"}],
          "jobFunctions": ["urn:li:function:12"],
          "seniorities": ["urn:li:seniority:8", "urn:li:seniority:9"]
        }
      },
      "creativeSelection": "OPTIMIZED",
      "created": 1719700000000,
      "lastModified": 1720500000000
    },
    {
      "id": 612345002,
      "name": "Lead Gen - Decision Makers",
      "account": "urn:li:sponsoredAccount:512345678",
      "status": "PAUSED",
      "type": "SPONSORED_UPDATES",
      "costType": "CPC",
      "objectiveType": "LEAD_GENERATION",
      "dailyBudget": {
        "amount": "150.00",
        "currencyCode": "USD"
      },
      "totalBudget": {
        "amount": "4500.00",
        "currencyCode": "USD"
      },
      "runSchedule": {
        "start": 1717200000000,
        "end": null
      },
      "unitCost": {
        "amount": "8.75",
        "currencyCode": "USD"
      },
      "targeting": {
        "includedTargetingFacets": {
          "locations": ["urn:li:geo:103644278"],
          "interfaceLocales": [{"country": "US", "language": "en"}],
          "titles": ["urn:li:title:100", "urn:li:title:200"]
        }
      },
      "creativeSelection": "OPTIMIZED",
      "created": 1717100000000,
      "lastModified": 1719000000000
    }
  ],
  "metadata": {
    "nextPageToken": null,
    "total": 2
  }
}
```

### GET /adAnalytics

Get campaign analytics data.

**Query parameters:**
- `q` — `analytics`
- `dateRange.start.day`, `dateRange.start.month`, `dateRange.start.year` — start date components
- `dateRange.end.day`, `dateRange.end.month`, `dateRange.end.year` — end date components
- `timeGranularity` — `DAILY`, `MONTHLY`, or `ALL`
- `campaigns[0]` — campaign URN (e.g., `urn:li:sponsoredCampaign:612345001`)
- `pivot` — `CAMPAIGN`, `CREATIVE`, `COMPANY`, `MEMBER_COMPANY_SIZE`, `MEMBER_COUNTRY_V2`, `MEMBER_REGION_V2`, `MEMBER_COUNTY`
- `fields` — comma-separated list of metrics to return (default: only `impressions` and `clicks`; request up to 20)
- `accounts` — account URN(s) in `List()` format (alternative to `campaigns`)

**Example request:**

```
GET /linkedin/rest/adAnalytics?q=analytics&dateRange.start.day=1&dateRange.start.month=6&dateRange.start.year=2026&dateRange.end.day=30&dateRange.end.month=6&dateRange.end.year=2026&timeGranularity=DAILY&campaigns[0]=urn:li:sponsoredCampaign:612345001&pivot=CAMPAIGN&start=0&count=30
```

**Response:**

```json
{
  "elements": [
    {
      "dateRange": {
        "start": {"day": 1, "month": 6, "year": 2026},
        "end": {"day": 2, "month": 6, "year": 2026}
      },
      "pivotValues": ["urn:li:sponsoredCampaign:612345001"],
      "impressions": 12500,
      "clicks": 185,
      "costInLocalCurrency": "2312.50",
      "costInUsd": "2312.50",
      "likes": 42,
      "comments": 8,
      "shares": 15,
      "follows": 5,
      "leadGenerationMailContactInfoShares": 0,
      "leadGenerationMailInterestedClicks": 0,
      "videoViews": 0,
      "videoCompletions": 0,
      "externalWebsiteConversions": 3,
      "oneClickLeads": 12
    },
    {
      "dateRange": {
        "start": {"day": 2, "month": 6, "year": 2026},
        "end": {"day": 3, "month": 6, "year": 2026}
      },
      "pivotValues": ["urn:li:sponsoredCampaign:612345001"],
      "impressions": 11800,
      "clicks": 172,
      "costInLocalCurrency": "2150.00",
      "costInUsd": "2150.00",
      "likes": 38,
      "comments": 5,
      "shares": 12,
      "follows": 3,
      "leadGenerationMailContactInfoShares": 0,
      "leadGenerationMailInterestedClicks": 0,
      "videoViews": 0,
      "videoCompletions": 0,
      "externalWebsiteConversions": 2,
      "oneClickLeads": 9
    }
  ],
  "paging": {
    "start": 0,
    "count": 30,
    "total": 30
  }
}
```

## Pagination

- **adAccounts (from version 202401+):** Cursor-based via `pageSize` and `pageToken` parameters. Response includes `metadata.nextPageToken`. Max `pageSize`: 1,000.
- **adCampaigns:** Cursor-based via `pageSize` and `pageToken` parameters. Response includes `metadata.nextPageToken`. Max `pageSize`: 1,000.
- **adAnalytics:** Does NOT support pagination. Response is limited to 15,000 elements.

```
adAccounts:
Page 1: GET /adAccounts?q=search&pageSize=100  → metadata.nextPageToken = "abc..."
Page 2: GET /adAccounts?q=search&pageSize=100&pageToken=abc...  → metadata.nextPageToken = null (done)

adCampaigns:
Page 1: GET /adAccounts/{id}/adCampaigns?q=search&pageSize=100  → metadata.nextPageToken = "xyz..."
Page 2: GET /adAccounts/{id}/adCampaigns?q=search&pageSize=100&pageToken=xyz...  → metadata.nextPageToken = null (done)
```

## Rate Limits

- Application-level and member-level limits (varies by endpoint and partner tier)
- Limits vary by partner status and endpoint
- HTTP 429 on exceeded with `Retry-After` header
- **adAnalytics data throttling:** 45 million metric values per 5-minute window. Use `fields` parameter to reduce data load.

## Error Responses

**401 Unauthorized:**
```json
{
  "status": 401,
  "serviceErrorCode": 65601,
  "code": "UNAUTHORIZED",
  "message": "The token used in the request has expired"
}
```

**403 Forbidden:**
```json
{
  "status": 403,
  "serviceErrorCode": 100,
  "code": "ACCESS_DENIED",
  "message": "Not enough permissions to access this resource"
}
```

**404 Not found:**
```json
{
  "status": 404,
  "serviceErrorCode": 0,
  "code": "RESOURCE_NOT_FOUND",
  "message": "Resource urn:li:sponsoredCampaign:999 does not exist"
}
```

**429 Rate limited:**
```json
{
  "status": 429,
  "serviceErrorCode": 0,
  "code": "THROTTLED",
  "message": "Too many requests. Please retry after some time."
}
```

## Notes

- URN format is used extensively: `urn:li:sponsoredAccount:512345678`, `urn:li:sponsoredCampaign:612345001`, `urn:li:organization:12345`
- Date ranges in analytics use component fields (day/month/year), not ISO strings
- Cost values are strings (not numbers) in analytics responses
- Timestamps are unix milliseconds (not seconds)
- Budget amounts are strings with decimal points
- `Linkedin-Version` header is **mandatory** — requests without it will fail
- Monthly versions; each supported for minimum 1 year before sunset
- Targeting uses facet URNs (geo, function, seniority, title) -- not human-readable names
- adAnalytics supports three finder methods: `analytics` (single pivot), `statistics` (up to 3 pivots), `attributedRevenueMetrics` (revenue attribution)
- By default, adAnalytics only returns `impressions` and `clicks` -- use `fields` parameter to request additional metrics

## Reference

- [Create and Manage Ad Accounts](https://learn.microsoft.com/en-us/linkedin/marketing/integrations/ads/account-structure/create-and-manage-accounts?view=li-lms-2026-06) -- adAccounts endpoint with cursor-based pagination
- [Create and Manage Campaigns](https://learn.microsoft.com/en-us/linkedin/marketing/integrations/ads/account-structure/create-and-manage-campaigns?view=li-lms-2026-06) -- adCampaigns endpoint
- [Reporting (Ad Analytics)](https://learn.microsoft.com/en-us/linkedin/marketing/integrations/ads-reporting/ads-reporting?view=li-lms-2026-06) -- adAnalytics endpoint, finder methods, metrics
- [API Versioning](https://learn.microsoft.com/en-us/linkedin/marketing/versioning?view=li-lms-2026-05) -- Linkedin-Version header and versioning policy
- [LinkedIn Marketing API Overview](https://learn.microsoft.com/en-us/linkedin/marketing/?view=li-lms-2026-06) -- API program overview
