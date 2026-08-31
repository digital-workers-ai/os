# Smartlook API v1

## Overview

Smartlook session recording and analytics API. Provides access to tracked events, session recordings, and visitor behavior data. **Deprecated** — Smartlook reached End of Sale May 31, 2026. API continues in maintenance mode.

## Base URL

```
US: https://api.us.smartlook.cloud
EU: https://api.eu.smartlook.cloud
```

Selected by `SMARTLOOK_REGION` setting (defaults to `"eu"`).

Mock server prefix: `/smartlook`

## Authentication

Bearer token via header.

```
Authorization: Bearer {SMARTLOOK_API_TOKEN}
Content-Type: application/json
```

Config keys: `SMARTLOOK_API_TOKEN`, `SMARTLOOK_REGION`

## Endpoints

### GET /api/v1/events

List all tracked events.

**Query parameters:**
- `limit` — number of results to return
- `after` — cursor for forward pagination
- `before` — cursor for backward pagination
- `categoryId` — filter by event category

**Response:**

```json
{
  "events": [
    {
      "id": "evt_click_signup",
      "name": "click_signup_button",
      "type": "custom",
      "created_at": "2026-01-15T10:00:00Z"
    },
    {
      "id": "evt_page_pricing",
      "name": "visit_pricing_page",
      "type": "custom",
      "created_at": "2026-02-01T14:30:00Z"
    },
    {
      "id": "evt_form_submit",
      "name": "form_submission",
      "type": "custom",
      "created_at": "2026-03-10T09:15:00Z"
    },
    {
      "id": "evt_rage_click",
      "name": "rage_click",
      "type": "system",
      "created_at": "2025-12-01T00:00:00Z"
    }
  ]
}
```

### GET /api/v1/events/{event_id}

Get event detail with histogram data.

**Query parameters:**
- `dateFrom` (required) — ISO 8601 datetime (e.g., `2026-06-01T00:00:00Z`)
- `dateTo` (required) — ISO 8601 datetime (e.g., `2026-06-30T23:59:59Z`)
- `occurrenceHistogramInterval` — interval for histogram bucketing (optional)

**Example request:**

```
GET /smartlook/api/v1/events/evt_click_signup?dateFrom=2026-06-01T00:00:00Z&dateTo=2026-06-30T23:59:59Z
```

**Response:**

```json
{
  "id": "evt_click_signup",
  "name": "click_signup_button",
  "type": "custom",
  "histogram": {
    "labels": ["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04", "2026-06-05"],
    "data": [45, 52, 38, 61, 55]
  },
  "total_count": 251,
  "unique_visitors": 198
}
```

### POST /api/v1/sessions/search

Search for recorded sessions with filters.

**Query parameters:**
- `limit` — page size (default/hardcoded 50)
- `after` — cursor for pagination

**Request body:**

```json
{
  "filters": [
    {
      "name": "recording_date",
      "operator": "in_range",
      "value": ["2026-06-01T00:00:00Z", "2026-06-30T23:59:59Z"]
    }
  ]
}
```

**Additional filter examples:**

```json
{
  "filters": [
    {
      "name": "recording_date",
      "operator": "in_range",
      "value": ["2026-06-01T00:00:00Z", "2026-06-30T23:59:59Z"]
    },
    {
      "name": "duration",
      "operator": "greater_than",
      "value": 30
    },
    {
      "name": "country",
      "operator": "is",
      "value": "US"
    }
  ]
}
```

**Response:**

```json
{
  "sessions": [
    {
      "id": "sess_abc123",
      "visitorId": "vis_xyz789",
      "duration": 185,
      "startedAt": "2026-06-15T14:32:10.000Z",
      "endedAt": "2026-06-15T14:35:15.000Z",
      "landingPage": "https://acme.io/pricing",
      "exitPage": "https://acme.io/signup",
      "referrer": "https://www.google.com/",
      "identification": {
        "browser": {
          "name": "Chrome",
          "version": "126.0"
        },
        "platform": {
          "name": "macOS",
          "version": "15.1"
        },
        "country": {
          "city": "San Francisco",
          "region": "California",
          "code": "US"
        },
        "device": {
          "type": "desktop"
        }
      },
      "pageUrl": [
        "https://acme.io/pricing",
        "https://acme.io/features",
        "https://acme.io/signup"
      ],
      "eventsCount": 12,
      "dashboardURL": "https://app.smartlook.com/recordings/sess_abc123"
    },
    {
      "id": "sess_def456",
      "visitorId": "vis_uvw321",
      "duration": 42,
      "startedAt": "2026-06-15T15:10:00.000Z",
      "endedAt": "2026-06-15T15:10:42.000Z",
      "landingPage": "https://acme.io/",
      "exitPage": "https://acme.io/",
      "referrer": "",
      "identification": {
        "browser": {
          "name": "Safari",
          "version": "18.0"
        },
        "platform": {
          "name": "iOS",
          "version": "19.0"
        },
        "country": {
          "city": "London",
          "region": "England",
          "code": "GB"
        },
        "device": {
          "type": "mobile"
        }
      },
      "pageUrl": [
        "https://acme.io/"
      ],
      "eventsCount": 3,
      "dashboardURL": "https://app.smartlook.com/recordings/sess_def456"
    }
  ],
  "pagination": {
    "after": "eyJsYXN0SWQiOiJzZXNzX2RlZjQ1NiJ9"
  }
}
```

**Last page (no more results):**

```json
{
  "sessions": [],
  "pagination": {
    "after": null
  }
}
```

### GET /api/v1/visitors/{visitor_id}/events

Get events for a specific visitor session.

**Query parameters:**
- `sessionId` — filter events to a specific session

**Example request:**

```
GET /smartlook/api/v1/visitors/vis_xyz789/events?sessionId=sess_abc123
```

**Response:**

```json
{
  "events": [
    {
      "type": "page_visit",
      "url": "https://acme.io/pricing",
      "timestamp": 1718458330000,
      "duration": 45000
    },
    {
      "type": "custom",
      "name": "visit_pricing_page",
      "timestamp": 1718458330500,
      "data": {}
    },
    {
      "type": "click",
      "selector": "button.cta-primary",
      "text": "Start Free Trial",
      "timestamp": 1718458375000
    },
    {
      "type": "page_visit",
      "url": "https://acme.io/features",
      "timestamp": 1718458376000,
      "duration": 60000
    },
    {
      "type": "custom",
      "name": "click_signup_button",
      "timestamp": 1718458436000,
      "data": {"plan": "growth"}
    },
    {
      "type": "page_visit",
      "url": "https://acme.io/signup",
      "timestamp": 1718458437000,
      "duration": 80000
    }
  ]
}
```

## Pagination

- **Mechanism:** Cursor-based via `pagination.after` in response
- **Page size:** `limit` query parameter (hardcoded to 50 in the real client)
- **To get next page:** Pass `after={cursor}` as query parameter on the POST request
- **Done when:** `pagination.after` is `null` or `sessions` array is empty

```
Page 1: POST /sessions/search?limit=50
         → pagination.after = "eyJsYXN0SWQiOi..."
Page 2: POST /sessions/search?limit=50&after=eyJsYXN0SWQiOi...
         → pagination.after = "eyJsYXN0SWQiOi..."
Page 3: POST /sessions/search?limit=50&after=eyJsYXN0SWQiOi...
         → pagination.after = null  (done)
```

## Error Responses

**401 Unauthorized:**
```json
{
  "error": "Unauthorized",
  "message": "Invalid or missing API token"
}
```

**429 Rate limited:**
```json
{
  "error": "Too Many Requests",
  "message": "Rate limit exceeded. Please retry after 30 seconds.",
  "retryAfter": 30
}
```

The 429 response body may contain a cooldown duration that the client parses.

**404 Not found:**
```json
{
  "error": "Not Found",
  "message": "Event not found"
}
```

## Rate Limits

- **Free plan:** 20 requests per hour
- **Paid plans:** 100 requests per hour
- **REST API add-on:** 1,000 requests per hour

Usage statistics available via the `/api/statistics` endpoint.

## Notes

- `startedAt`/`endedAt` can be either ISO strings or unix milliseconds — the client handles both
- `duration` is in seconds
- Event timestamps in visitor events are unix milliseconds
- The `dashboardURL` links to the Smartlook web dashboard for that recording
- `identification` has a nested structure for browser, platform, country, and device
- Retry: 3 attempts, exponential backoff 1-4s, on 429/500/502/503 (via shared `with_retry` tenacity decorator)
- **Deprecation:** Smartlook reaches End of Sale May 31, 2026. API in maintenance mode only.

## Reference

- [API Overview](https://integrations.smartlook.com/docs/api-overview) -- Base URL, authentication, rate limits
- [Search Sessions](https://integrations.smartlook.com/reference/searchsessions) -- POST /api/v1/sessions/search endpoint
- [Get Events List](https://integrations.smartlook.com/reference/geteventslist) -- GET /api/v1/events endpoint
- [Get Event Details](https://integrations.smartlook.com/reference/geteventdetail) -- GET /api/v1/events/{eventId} endpoint
- [Searching Sessions guide](https://integrations.smartlook.com/docs/search-user-sessions) -- Filter and sort options for session search
