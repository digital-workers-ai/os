# Customer.io App API

## Overview

Customer.io's App API provides access to campaigns, newsletters, segments, activities, and messaging metrics. Used by OS for email/messaging engagement data.

- **Category:** Email / Messaging
- **Production Base URL:** `https://api.customer.io` (US) or `https://api-eu.customer.io` (EU)
- **Mock Base URL:** `http://localhost:8100/customerio`
- **Response Format:** JSON

## Authentication

Bearer token in the `Authorization` header:

```
Authorization: Bearer cio_app_api_key_here
Content-Type: application/json
```

### Mock Server Token

The mock server accepts any token starting with `cio_mock_`.

```bash
curl -H "Authorization: Bearer cio_mock_test_key" \
  "http://localhost:8100/customerio/v1/campaigns"
```

---

## Endpoints

### 1. List Campaigns

```
GET /v1/campaigns
```

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cursor` | string | — | Pagination cursor (from `next_cursor` in response) |
| `limit` | integer | 100 | Results per page (max 1000) |

**Example request:**

```bash
curl -H "Authorization: Bearer cio_app_api_key" \
  "https://api.customer.io/v1/campaigns?limit=3"
```

**Example response (200) — with more pages:**

```json
{
  "campaigns": [
    {
      "id": 101,
      "name": "Welcome Series",
      "type": "triggered",
      "active": true,
      "created": 1710500000,
      "updated": 1720000000,
      "tags": ["onboarding", "email"],
      "msg_templates_count": 4,
      "actions_count": 6
    },
    {
      "id": 102,
      "name": "Trial Expiry Reminder",
      "type": "triggered",
      "active": true,
      "created": 1712000000,
      "updated": 1719000000,
      "tags": ["conversion", "email"],
      "msg_templates_count": 2,
      "actions_count": 3
    },
    {
      "id": 103,
      "name": "Monthly Product Update",
      "type": "segment_triggered",
      "active": true,
      "created": 1715000000,
      "updated": 1721000000,
      "tags": ["engagement", "email"],
      "msg_templates_count": 1,
      "actions_count": 2
    }
  ],
  "next_cursor": "camp_104"
}
```

**Example response (200) — last page:**

```json
{
  "campaigns": [
    {
      "id": 106,
      "name": "Re-engagement Flow",
      "type": "triggered",
      "active": false,
      "created": 1718000000,
      "updated": 1720000000,
      "tags": ["win-back"],
      "msg_templates_count": 3,
      "actions_count": 5
    }
  ]
}
```

Note: When there are no more pages, `next_cursor` is **absent** from the response.

---

### 2. Campaign Metrics

```
GET /v1/campaigns/{campaign_id}/metrics
```

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `period` | string | `"days"` | Time bucket size: `"days"`, `"weeks"`, or `"months"` |
| `steps` | integer | 1 | Number of periods to return |
| `start` | integer | — | Unix timestamp for range start |
| `end` | integer | — | Unix timestamp for range end |
| `resolution` | string | — | Alias for `period` in some endpoints |
| `timezone` | string | `"UTC"` | IANA timezone for bucketing |

**Example request:**

```bash
curl -H "Authorization: Bearer cio_app_api_key" \
  "https://api.customer.io/v1/campaigns/101/metrics?period=months&steps=3"
```

**Example response (200):**

```json
{
  "metric": {
    "series": {
      "sent": [150, 140, 160],
      "delivered": [145, 135, 155],
      "opened": [80, 70, 90],
      "clicked": [30, 25, 35],
      "bounced": [5, 5, 5],
      "unsubscribed": [2, 1, 3],
      "spammed": [0, 0, 1],
      "converted": [12, 10, 15],
      "dropped": [0, 0, 0]
    },
    "start": "2026-04-01 00:00:00 +0000 UTC",
    "end": "2026-07-01 00:00:00 +0000 UTC"
  }
}
```

Each array in `series` has `steps` elements. Arrays are aligned — index 0 is the first period, index 1 is the second, etc.

---

### 3. List Activities

```
GET /v1/activities
```

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `start` | string | — | Pagination cursor (from `next_cursor` in response) |
| `limit` | integer | 100 | Results per page |
| `type` | string | — | Filter by activity type (e.g., `"email_opened"`) |

Note: Activities use `start` as the cursor parameter, not `cursor`.

**Example request:**

```bash
curl -H "Authorization: Bearer cio_app_api_key" \
  "https://api.customer.io/v1/activities?limit=3"
```

**Example response (200):**

```json
{
  "activities": [
    {
      "type": "email_sent",
      "delivery_id": "del_001",
      "timestamp": 1720500000,
      "customer_id": "user_jane_acme",
      "campaign_name": "Welcome Series",
      "campaign_id": 101,
      "data": {
        "template_id": 201,
        "subject": "Welcome to the platform!"
      }
    },
    {
      "type": "email_opened",
      "delivery_id": "del_001",
      "timestamp": 1720503600,
      "customer_id": "user_jane_acme",
      "campaign_name": "Welcome Series",
      "campaign_id": 101,
      "data": {
        "template_id": 201
      }
    },
    {
      "type": "email_clicked",
      "delivery_id": "del_001",
      "timestamp": 1720507200,
      "customer_id": "user_jane_acme",
      "campaign_name": "Welcome Series",
      "campaign_id": 101,
      "data": {
        "template_id": 201,
        "link_url": "https://app.example.com/getting-started"
      }
    }
  ],
  "next_cursor": "act_004"
}
```

### Activity Types

| Type | Description |
|------|-------------|
| `email_sent` | Email was sent |
| `email_delivered` | Email was delivered |
| `email_opened` | Email was opened |
| `email_clicked` | Link in email was clicked |
| `email_bounced` | Email bounced |
| `email_unsubscribed` | Recipient unsubscribed |
| `email_spammed` | Marked as spam |
| `push_sent` | Push notification sent |
| `push_opened` | Push notification opened |
| `sms_sent` | SMS was sent |
| `sms_delivered` | SMS was delivered |
| `webhook_sent` | Webhook was triggered |

---

### 4. List Newsletters (Broadcasts)

```
GET /v1/newsletters
```

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cursor` | string | — | Pagination cursor |
| `limit` | integer | 100 | Results per page |

**Example response (200):**

```json
{
  "newsletters": [
    {
      "id": 501,
      "name": "July Product Update",
      "type": "email",
      "created": 1719500000,
      "updated": 1720000000,
      "sent_at": 1720000000,
      "tags": ["product-update", "monthly"],
      "recipient_count": 5200
    },
    {
      "id": 502,
      "name": "Q2 Customer Survey",
      "type": "email",
      "created": 1717000000,
      "updated": 1717500000,
      "sent_at": 1717500000,
      "tags": ["survey"],
      "recipient_count": 4800
    }
  ],
  "next_cursor": "news_503"
}
```

---

### 5. List Segments

```
GET /v1/segments
```

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cursor` | string | — | Pagination cursor |
| `limit` | integer | 100 | Results per page |

**Example response (200):**

```json
{
  "segments": [
    {
      "id": 10,
      "name": "Active Customers",
      "description": "Customers who logged in within the last 30 days",
      "type": "dynamic",
      "state": "finished",
      "progress": 100,
      "count": 1250
    },
    {
      "id": 11,
      "name": "Trial Users",
      "description": "Users currently in trial period",
      "type": "dynamic",
      "state": "finished",
      "progress": 100,
      "count": 340
    },
    {
      "id": 12,
      "name": "Churned Q1",
      "description": "Customers who canceled in Q1 2026",
      "type": "manual",
      "state": "finished",
      "progress": 100,
      "count": 87
    }
  ]
}
```

---

### 6. Campaign Link Metrics

```
GET /v1/campaigns/{campaign_id}/metrics/links
```

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `period` | string | `"days"` | `"days"`, `"weeks"`, or `"months"` |
| `steps` | integer | 1 | Number of periods |
| `unique` | boolean | false | Count unique clicks only |

**Example response (200):**

```json
{
  "links": [
    {
      "link": "https://app.example.com/getting-started",
      "clicks": 145,
      "unique_clicks": 120
    },
    {
      "link": "https://app.example.com/docs",
      "clicks": 87,
      "unique_clicks": 75
    }
  ]
}
```

---

## Pagination

Customer.io uses **cursor-based pagination** with two different cursor parameter names depending on the endpoint.

### Cursor Parameter Names

| Endpoints | Cursor query param | Cursor response field |
|-----------|-------------------|----------------------|
| `/campaigns`, `/newsletters`, `/segments` | `cursor` | `next_cursor` |
| `/activities`, `/campaigns/{id}/messages`, `/segments/{id}/membership` | `start` | `next_cursor` |

### How it works

1. Make initial request (optionally with `limit`)
2. If response contains `next_cursor`, pass that value as `cursor` (or `start`, depending on endpoint)
3. Repeat until `next_cursor` is **absent** from the response

### Rules

- `limit` range varies by endpoint (up to 1000 for campaigns, 100 for activities)
- When there are no more results, `next_cursor` is omitted entirely (not null)
- The response item key matches the resource name (`campaigns`, `newsletters`, `segments`, `activities`)

### Pseudocode

```python
campaigns = []
cursor = None
while True:
    params = {"limit": 100}
    if cursor:
        params["cursor"] = cursor
    response = get("/v1/campaigns", params=params)
    campaigns.extend(response["campaigns"])
    cursor = response.get("next_cursor")
    if not cursor:
        break
```

---

## Error Responses

### 401 Unauthorized

```json
{
  "meta": {
    "error": "Unauthorized",
    "status": 401
  }
}
```

### 404 Not Found

```json
{
  "meta": {
    "error": "Not Found",
    "status": 404
  }
}
```

### 429 Rate Limit

```json
{
  "meta": {
    "error": "Rate limit exceeded. Please retry after 1 second.",
    "status": 429
  }
}
```

---

## Notes

- Customer.io has both a Track API (for sending events/identifying users) and an App API (for reading data). This doc covers the **App API** only
- Region selection (US vs EU) is set at the workspace level. The base URL changes accordingly
- Metric `series` arrays are always aligned: each index corresponds to the same time period across all metric keys
- Timestamps in campaign/newsletter objects are Unix timestamps (integers)
- Timestamps in the metrics `start`/`end` fields use the format `"YYYY-MM-DD HH:MM:SS +0000 UTC"`
- The App API is async (`httpx.AsyncClient` in dashboard-dbb). The mock server serves sync responses since FastAPI handles async transparently
- The old beta API used paths like `/v1/api/campaigns` at `https://beta-api.customer.io`. The production API uses `/v1/campaigns` at `https://api.customer.io`

---

## Reference

- [About Customer.io's APIs](https://docs.customer.io/integrations/api/customerio-apis/) -- Overview of API types, base URLs, and authentication methods
- [App API Reference](https://docs.customer.io/integrations/api/app/) -- Full App API endpoint reference
- [Customer.io OpenAPI Spec](https://raw.githubusercontent.com/api-evangelist/customerio/refs/heads/main/openapi/customerio-openapi.yml) -- OpenAPI specification with endpoint paths and base URLs
- [Customer.io App/Transactional API (APIs.io)](https://apis.io/apis/customerio/app-transactional-api/) -- API metadata and specification links
