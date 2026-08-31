# Google Analytics 4 (GA4) — Data API v1beta

## Overview

Google Analytics 4 Data API for fetching analytics reports. All data fetching goes through a single `runReport` POST endpoint. Uses positional arrays for dimensions and metrics in the response.

## Base URL

```
https://analyticsdata.googleapis.com/v1beta
```

Mock server prefix: `/ga4/v1beta`

## Authentication

OAuth 2.0 Bearer token or Google Service Account credentials.

```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**OAuth token refresh:**
```
POST https://oauth2.googleapis.com/token
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token&refresh_token={token}&client_id={id}&client_secret={secret}
```

**Required scope:** `https://www.googleapis.com/auth/analytics.readonly`

## Endpoints

### POST /properties/{property_id}:runReport

The only data endpoint. All report types use this with different dimension/metric combinations.

**Request body:**

```json
{
  "dateRanges": [
    {
      "startDate": "2026-06-01",
      "endDate": "2026-06-30"
    }
  ],
  "dimensions": [
    {"name": "date"},
    {"name": "sessionDefaultChannelGroup"}
  ],
  "metrics": [
    {"name": "sessions"},
    {"name": "newUsers"},
    {"name": "activeUsers"},
    {"name": "screenPageViews"},
    {"name": "engagementRate"},
    {"name": "averageSessionDuration"}
  ],
  "limit": 10000,
  "offset": 0
}
```

**Response:**

```json
{
  "dimensionHeaders": [
    {"name": "date"},
    {"name": "sessionDefaultChannelGroup"}
  ],
  "metricHeaders": [
    {"name": "sessions", "type": "TYPE_INTEGER"},
    {"name": "newUsers", "type": "TYPE_INTEGER"},
    {"name": "activeUsers", "type": "TYPE_INTEGER"},
    {"name": "screenPageViews", "type": "TYPE_INTEGER"},
    {"name": "engagementRate", "type": "TYPE_FLOAT"},
    {"name": "averageSessionDuration", "type": "TYPE_SECONDS"}
  ],
  "rows": [
    {
      "dimensionValues": [
        {"value": "20260601"},
        {"value": "Organic Search"}
      ],
      "metricValues": [
        {"value": "1250"},
        {"value": "430"},
        {"value": "980"},
        {"value": "3200"},
        {"value": "0.6432"},
        {"value": "185.4"}
      ]
    },
    {
      "dimensionValues": [
        {"value": "20260601"},
        {"value": "Direct"}
      ],
      "metricValues": [
        {"value": "820"},
        {"value": "210"},
        {"value": "650"},
        {"value": "1800"},
        {"value": "0.5891"},
        {"value": "142.7"}
      ]
    },
    {
      "dimensionValues": [
        {"value": "20260601"},
        {"value": "Paid Search"}
      ],
      "metricValues": [
        {"value": "540"},
        {"value": "380"},
        {"value": "420"},
        {"value": "1100"},
        {"value": "0.5120"},
        {"value": "98.3"}
      ]
    }
  ],
  "rowCount": 3,
  "kind": "analyticsData#runReport",
  "metadata": {
    "currencyCode": "USD",
    "timeZone": "America/Los_Angeles"
  }
}
```

## Example Report Requests

### Channel Report

```json
{
  "dateRanges": [{"startDate": "2026-06-01", "endDate": "2026-06-30"}],
  "dimensions": [{"name": "date"}, {"name": "sessionDefaultChannelGroup"}],
  "metrics": [
    {"name": "newUsers"}, {"name": "sessions"}, {"name": "screenPageViews"},
    {"name": "engagementRate"}, {"name": "averageSessionDuration"}, {"name": "activeUsers"}
  ],
  "limit": 10000,
  "offset": 0
}
```

### Landing Pages Report

```json
{
  "dateRanges": [{"startDate": "2026-06-01", "endDate": "2026-06-30"}],
  "dimensions": [{"name": "date"}, {"name": "landingPage"}],
  "metrics": [
    {"name": "sessions"}, {"name": "keyEvents"}, {"name": "engagementRate"}
  ],
  "limit": 10000,
  "offset": 0
}
```

### Device Report

```json
{
  "dateRanges": [{"startDate": "2026-06-01", "endDate": "2026-06-30"}],
  "dimensions": [{"name": "date"}, {"name": "deviceCategory"}],
  "metrics": [{"name": "sessions"}],
  "limit": 10000,
  "offset": 0
}
```

### Geo Report

```json
{
  "dateRanges": [{"startDate": "2026-06-01", "endDate": "2026-06-30"}],
  "dimensions": [{"name": "date"}, {"name": "city"}, {"name": "region"}],
  "metrics": [{"name": "sessions"}],
  "limit": 10000,
  "offset": 0
}
```

### Source/Medium Report

```json
{
  "dateRanges": [{"startDate": "2026-06-01", "endDate": "2026-06-30"}],
  "dimensions": [{"name": "date"}, {"name": "sessionSourceMedium"}],
  "metrics": [
    {"name": "sessions"}, {"name": "newUsers"}, {"name": "engagementRate"}, {"name": "keyEvents"}
  ],
  "limit": 10000,
  "offset": 0
}
```

### Hourly Report

```json
{
  "dateRanges": [{"startDate": "2026-06-01", "endDate": "2026-06-30"}],
  "dimensions": [{"name": "dateHour"}, {"name": "dayOfWeek"}],
  "metrics": [{"name": "sessions"}],
  "limit": 10000,
  "offset": 0
}
```

Response uses `dateHour` format `YYYYMMDDHH` (e.g., `"2026060114"` = June 1 at 2 PM).

### Cohort Retention Report

```json
{
  "dimensions": [
    {"name": "cohort"},
    {"name": "cohortNthWeek"}
  ],
  "metrics": [
    {"name": "cohortActiveUsers"},
    {"name": "cohortTotalUsers"}
  ],
  "cohortSpec": {
    "cohorts": [
      {
        "name": "cohort_week_1",
        "dimension": "firstSessionDate",
        "dateRange": {"startDate": "2026-05-01", "endDate": "2026-05-07"}
      },
      {
        "name": "cohort_week_2",
        "dimension": "firstSessionDate",
        "dateRange": {"startDate": "2026-05-08", "endDate": "2026-05-14"}
      }
    ],
    "cohortsRange": {
      "endOffset": 5,
      "granularity": "WEEKLY"
    }
  }
}
```

**Cohort response:**

```json
{
  "dimensionHeaders": [
    {"name": "cohort"},
    {"name": "cohortNthWeek"}
  ],
  "metricHeaders": [
    {"name": "cohortActiveUsers", "type": "TYPE_INTEGER"},
    {"name": "cohortTotalUsers", "type": "TYPE_INTEGER"}
  ],
  "rows": [
    {
      "dimensionValues": [{"value": "cohort_week_1"}, {"value": "0000"}],
      "metricValues": [{"value": "500"}, {"value": "500"}]
    },
    {
      "dimensionValues": [{"value": "cohort_week_1"}, {"value": "0001"}],
      "metricValues": [{"value": "320"}, {"value": "500"}]
    },
    {
      "dimensionValues": [{"value": "cohort_week_1"}, {"value": "0002"}],
      "metricValues": [{"value": "210"}, {"value": "500"}]
    }
  ],
  "rowCount": 3,
  "metadata": {
    "currencyCode": "USD",
    "timeZone": "America/Los_Angeles"
  }
}
```

## Pagination

- **Mechanism:** Offset-based via `limit` and `offset` in request body (no token-based pagination)
- **Page size:** Set via `limit` in request body (default: 10,000; max: 250,000)
- **To get next page:** Set `offset` = current offset + number of rows received
- **Done when:** `offset` + rows received >= `rowCount` from the response

```
Page 1: POST body { limit: 10000, offset: 0 }     → response rowCount: 25000
Page 2: POST body { limit: 10000, offset: 10000 }  → response rowCount: 25000
Page 3: POST body { limit: 10000, offset: 20000 }  → offset + rows >= rowCount = done
```

## Error Responses

**401 Unauthorized:**
```json
{
  "error": {
    "code": 401,
    "message": "Request had invalid authentication credentials.",
    "status": "UNAUTHENTICATED"
  }
}
```

**403 Forbidden (wrong property):**
```json
{
  "error": {
    "code": 403,
    "message": "User does not have sufficient permissions for this property.",
    "status": "PERMISSION_DENIED"
  }
}
```

**429 Rate limited:**
```json
{
  "error": {
    "code": 429,
    "message": "Quota exceeded for quota metric 'Tokens per project per property'.",
    "status": "RESOURCE_EXHAUSTED"
  }
}
```

**400 Bad request (invalid dimension/metric):**
```json
{
  "error": {
    "code": 400,
    "message": "Incompatible dimensions and metrics: sessionDefaultChannelGroup is not compatible with cohortActiveUsers.",
    "status": "INVALID_ARGUMENT"
  }
}
```

## Notes

- Date format in dimension values is `YYYYMMDD` (no dashes): `"20260701"` not `"2026-07-01"`
- `dateHour` format is `YYYYMMDDHH`: `"2026070114"` = July 1 at 2 PM
- All metric values are returned as strings, even integers
- `engagementRate` is a float between 0 and 1 (not a percentage)
- `averageSessionDuration` is in seconds
- The real API uses Google API client library (`analyticsdata v1beta`), but the mock serves the same JSON over plain HTTP
- Config: `GA4_PROPERTY_ID` (numeric property ID, e.g., `"350123456"`)

## Reference

- [Method: properties.runReport](https://developers.google.com/analytics/devguides/reporting/data/v1/rest/v1beta/properties/runReport) -- RunReport request parameters and method details
- [RunReportResponse](https://developers.google.com/analytics/devguides/reporting/data/v1/rest/v1beta/RunReportResponse) -- Response object field definitions
- [MetricType enum](https://developers.google.com/analytics/devguides/reporting/data/v1/rest/v1beta/MetricType) -- All metric type values
- [Create a report](https://developers.google.com/analytics/devguides/reporting/data/v1/basics) -- Report creation guide with pagination examples
- [Data API limits and quotas](https://developers.google.com/analytics/devguides/reporting/data/v1/quotas) -- Rate limits and quota information
