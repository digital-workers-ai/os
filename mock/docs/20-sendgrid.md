# SendGrid API (Twilio)

## Overview

SendGrid v3 API provides access to marketing contacts, single sends (campaigns), email statistics, suppressions, and transactional email for Twilio's email delivery platform.

## Base URL

```
https://api.sendgrid.com
```

## Authentication

Bearer token (API key) in the Authorization header.

```
Authorization: Bearer {api_key}
Content-Type: application/json
```

Returns 401 without a valid key:
```json
{
  "errors": [
    {
      "message": "authorization required",
      "field": null,
      "help": null
    }
  ]
}
```

## Rate Limits

- Varies by endpoint (each endpoint has its own fixed request allowance per refresh period)
- HTTP 429 when exceeded (body: `{"errors":[{"message":"too many requests"}]}`)
- Rate limit headers on every response: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` (unix timestamp)

---

## Endpoints

### GET /v3/marketing/contacts

Returns all marketing contacts.

**Query Parameters:**

This endpoint does not support query-string pagination. For large contact lists, use the export endpoint instead.

**Example Request:**
```bash
curl -H "Authorization: Bearer sg_mock_apikey_001" \
  "https://api.sendgrid.com/v3/marketing/contacts"
```

**Example Response:**
```json
{
  "result": [
    {
      "id": "sg_contact_jane_001",
      "first_name": "Jane",
      "last_name": "Smith",
      "email": "jane@acme.io",
      "alternate_emails": [],
      "address_line_1": "123 Main St",
      "address_line_2": "",
      "city": "New York",
      "state_province_region": "NY",
      "postal_code": "10001",
      "country": "US",
      "phone_number": "+12125550100",
      "whatsapp": "",
      "line": "",
      "facebook": "",
      "unique_name": "jane_acme",
      "list_ids": ["sg_list_newsletter_001", "sg_list_customers_001"],
      "segment_ids": ["sg_seg_active_001"],
      "custom_fields": {
        "company": "Acme Corp",
        "plan": "enterprise",
        "mrr": "4800"
      },
      "created_at": "2025-03-20T14:30:00Z",
      "updated_at": "2026-07-10T09:00:00Z",
      "_metadata": {
        "self": "https://api.sendgrid.com/v3/marketing/contacts/sg_contact_jane_001"
      }
    },
    {
      "id": "sg_contact_bob_001",
      "first_name": "Bob",
      "last_name": "Smith",
      "email": "bob@soylent.co",
      "alternate_emails": ["robert.smith@soylent.co"],
      "address_line_1": "",
      "address_line_2": "",
      "city": "San Francisco",
      "state_province_region": "CA",
      "postal_code": "94102",
      "country": "US",
      "phone_number": "",
      "whatsapp": "",
      "line": "",
      "facebook": "",
      "unique_name": "bob_soylent",
      "list_ids": ["sg_list_newsletter_001"],
      "segment_ids": [],
      "custom_fields": {
        "company": "Soylent Corp",
        "plan": "growth",
        "mrr": "1200"
      },
      "created_at": "2025-06-10T09:00:00Z",
      "updated_at": "2026-06-15T12:00:00Z",
      "_metadata": {
        "self": "https://api.sendgrid.com/v3/marketing/contacts/sg_contact_bob_001"
      }
    }
  ],
  "contact_count": 15420,
  "_metadata": {
    "self": "https://api.sendgrid.com/v3/marketing/contacts"
  }
}
```

---

### GET /v3/marketing/singlesends

Returns all single sends (one-time campaigns).

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page_size` | int | 25 | Results per page (1-50) |
| `page_token` | string | — | Pagination token from `_metadata.next` |

**Example Request:**
```bash
curl -H "Authorization: Bearer sg_mock_apikey_001" \
  "https://api.sendgrid.com/v3/marketing/singlesends?page_size=2"
```

**Example Response:**
```json
{
  "result": [
    {
      "id": "sg_ss_welcome_001",
      "name": "Welcome Email - July 2026",
      "status": "triggered",
      "categories": ["welcome", "onboarding"],
      "send_at": "2026-07-10T14:00:00Z",
      "created_at": "2026-07-05T10:00:00Z",
      "updated_at": "2026-07-10T14:05:00Z",
      "is_abtest": false,
      "abtest": null,
      "send_to": {
        "list_ids": ["sg_list_newsletter_001"],
        "segment_ids": [],
        "all": false
      },
      "email_config": {
        "subject": "Welcome to Acme! Here's what you need to know",
        "html_content": "<html>...</html>",
        "plain_content": "Welcome to Acme...",
        "generate_plain_content": true,
        "editor": "design",
        "suppression_group_id": 101,
        "custom_unsubscribe_url": "",
        "sender_id": 201,
        "ip_pool": ""
      },
      "stats": {
        "total": {
          "requests": 1250,
          "delivered": 1235,
          "opens": 456,
          "unique_opens": 380,
          "clicks": 142,
          "unique_clicks": 118,
          "bounces": 15,
          "spam_reports": 2,
          "unsubscribes": 8,
          "bounce_drops": 0,
          "spam_report_drops": 0,
          "unsubscribe_drops": 0
        }
      }
    }
  ],
  "_metadata": {
    "self": "https://api.sendgrid.com/v3/marketing/singlesends?page_size=2",
    "next": "https://api.sendgrid.com/v3/marketing/singlesends?page_size=2&page_token=eyJsYXN0X2lk",
    "prev": null,
    "count": 45
  }
}
```

---

### GET /v3/stats

Returns global email statistics.

**Query Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `start_date` | string | Yes | YYYY-MM-DD format |
| `end_date` | string | No | YYYY-MM-DD format (default: today) |
| `aggregated_by` | string | No | `day`, `week`, or `month` |
| `limit` | int | No | Max results (default 500) |
| `offset` | int | No | Starting position |

**Example Request:**
```bash
curl -H "Authorization: Bearer sg_mock_apikey_001" \
  "https://api.sendgrid.com/v3/stats?start_date=2026-07-01&end_date=2026-07-07&aggregated_by=day"
```

**Example Response:**
```json
[
  {
    "date": "2026-07-01",
    "stats": [
      {
        "type": "category",
        "name": "all",
        "metrics": {
          "blocks": 2,
          "bounce_drops": 0,
          "bounces": 5,
          "clicks": 185,
          "deferred": 12,
          "delivered": 1235,
          "invalid_emails": 0,
          "opens": 580,
          "processed": 1250,
          "requests": 1250,
          "spam_report_drops": 0,
          "spam_reports": 2,
          "unique_clicks": 142,
          "unique_opens": 456,
          "unsubscribe_drops": 0,
          "unsubscribes": 8
        }
      }
    ]
  },
  {
    "date": "2026-07-02",
    "stats": [
      {
        "type": "category",
        "name": "all",
        "metrics": {
          "blocks": 1,
          "bounce_drops": 0,
          "bounces": 3,
          "clicks": 210,
          "deferred": 8,
          "delivered": 1340,
          "invalid_emails": 0,
          "opens": 620,
          "processed": 1355,
          "requests": 1355,
          "spam_report_drops": 0,
          "spam_reports": 1,
          "unique_clicks": 165,
          "unique_opens": 498,
          "unsubscribe_drops": 0,
          "unsubscribes": 5
        }
      }
    ]
  }
]
```

---

### GET /v3/marketing/lists

Returns all contact lists.

**Example Request:**
```bash
curl -H "Authorization: Bearer sg_mock_apikey_001" \
  "https://api.sendgrid.com/v3/marketing/lists?page_size=10"
```

**Example Response:**
```json
{
  "result": [
    {
      "id": "sg_list_newsletter_001",
      "name": "Newsletter Subscribers",
      "contact_count": 15420,
      "created_at": "2025-03-15T10:00:00Z",
      "updated_at": "2026-07-14T09:15:00Z",
      "_metadata": {
        "self": "https://api.sendgrid.com/v3/marketing/lists/sg_list_newsletter_001"
      }
    },
    {
      "id": "sg_list_customers_001",
      "name": "Active Customers",
      "contact_count": 4200,
      "created_at": "2025-04-01T10:00:00Z",
      "updated_at": "2026-07-13T16:00:00Z",
      "_metadata": {
        "self": "https://api.sendgrid.com/v3/marketing/lists/sg_list_customers_001"
      }
    }
  ],
  "_metadata": {
    "self": "https://api.sendgrid.com/v3/marketing/lists",
    "count": 5
  }
}
```

---

## Pagination

Mixed pagination depending on endpoint:

### Token-based (Single Sends, Lists)
```json
{
  "result": [...],
  "_metadata": {
    "self": "https://api.sendgrid.com/v3/marketing/singlesends?page_size=10",
    "next": "https://api.sendgrid.com/v3/marketing/singlesends?page_size=10&page_token=abc123",
    "prev": null,
    "count": 45
  }
}
```
- Follow `_metadata.next` URL for the next page
- `_metadata.count` gives total items
- Done when `_metadata.next` is `null`

### Offset-based (Stats)
```
GET /v3/stats?limit=500&offset=0
GET /v3/stats?limit=500&offset=500
```

### No pagination (Contacts)
The `/v3/marketing/contacts` endpoint returns all contacts at once. For large sets, use the async export endpoint.

## Error Responses

```json
{
  "errors": [
    {
      "message": "The start_date parameter is required.",
      "field": "start_date",
      "help": "https://sendgrid.api-docs.io/v3.0/stats"
    }
  ]
}
```

| HTTP Status | Meaning |
|-------------|---------|
| 400 | Bad request / missing required parameter |
| 401 | Unauthorized — missing or invalid API key |
| 403 | Forbidden — insufficient permissions |
| 404 | Resource not found |
| 413 | Payload too large |
| 429 | Rate limit exceeded |
| 500 | Internal server error |

## Notes

- Stats endpoint returns a **flat array** (not wrapped in an object), unlike other endpoints
- `contact_count` is available on lists — no need to fetch all contacts to get a count
- Single sends `status` values: `draft`, `scheduled`, `triggered` (sent)
- Custom fields on contacts are returned as string values regardless of original type
- The contacts endpoint does NOT paginate — returns all contacts up to a limit. For large sets (>50K), use `PUT /v3/marketing/contacts/exports` for async export
- `_metadata` is present on most responses with self-referencing URLs
- Metric names in stats: `requests` = attempted sends, `processed` = accepted by SendGrid, `delivered` = accepted by recipient's mail server
- All timestamps are UTC with Z suffix
- SendGrid docs have migrated from `docs.sendgrid.com` to `www.twilio.com/docs/sendgrid/`

## Reference

- [SendGrid v3 API Reference](https://www.twilio.com/docs/sendgrid/api-reference)
- [Authentication](https://www.twilio.com/docs/sendgrid/api-reference/how-to-use-the-sendgrid-v3-api/authentication)
- [Rate Limits](https://www.twilio.com/docs/sendgrid/api-reference/how-to-use-the-sendgrid-v3-api/rate-limits)
- [Get All Single Sends](https://www.twilio.com/docs/sendgrid/api-reference/single-sends/get-all-single-sends)
- [Get All Single Sends Stats](https://www.twilio.com/docs/sendgrid/api-reference/marketing-campaign-stats/get-all-single-sends-stats)
- [Getting Started with the SendGrid API](https://www.twilio.com/docs/sendgrid/for-developers/sending-email/api-getting-started)
