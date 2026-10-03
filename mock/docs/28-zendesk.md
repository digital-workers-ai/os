# Zendesk Support API

> API Version: v2
> Category: Support / Helpdesk

---

## Base URL

```
https://{subdomain}.zendesk.com/api/v2/
```

## Authentication

Two methods supported:

### Basic Auth (API token)

```
Authorization: Basic base64({email}/token:{api_token})
```

```bash
curl -u "admin@acme.io/token:zd_api_token_mock_xxxxxxxxxxxx" \
  "https://acme.zendesk.com/api/v2/tickets.json"
```

### OAuth Bearer Token

```
Authorization: Bearer zd_oauth_mock_xxxxxxxxxxxx
```

Returns `401 Unauthorized` without valid credentials.

---

## Endpoints

### GET /tickets.json

List tickets.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page[size]` | int | 100 | Items per page (max 100) |
| `page[after]` | string | — | Cursor from `meta.after_cursor` |
| `sort` | string | — | Sort field: `updated_at`, `id`, `status` (prefix `-` for desc, e.g. `-updated_at`) |
| `external_id` | string | — | Filter by external ID |

**Example Request:**

```bash
curl -u "admin@acme.io/token:zd_api_token_mock_xxxxxxxxxxxx" \
  "https://acme.zendesk.com/api/v2/tickets.json?page[size]=2"
```

**Example Response:**

```json
{
  "tickets": [
    {
      "id": 1001,
      "url": "https://acme.zendesk.com/api/v2/tickets/1001.json",
      "external_id": null,
      "type": "problem",
      "subject": "Cannot access billing dashboard",
      "raw_subject": "Cannot access billing dashboard",
      "description": "Hi, I'm unable to access the billing section of my account. I keep getting a 403 error.",
      "priority": "high",
      "status": "open",
      "recipient": "support@acme.io",
      "requester_id": 20001,
      "submitter_id": 20001,
      "assignee_id": 30001,
      "organization_id": 40001,
      "group_id": 50001,
      "collaborator_ids": [],
      "follower_ids": [],
      "email_cc_ids": [],
      "forum_topic_id": null,
      "problem_id": null,
      "has_incidents": false,
      "is_public": true,
      "due_at": null,
      "tags": ["billing", "access-issue", "high-priority"],
      "custom_fields": [
        {
          "id": 360001,
          "value": "acme.io"
        },
        {
          "id": 360002,
          "value": "growth"
        },
        {
          "id": 360003,
          "value": "browser_error"
        }
      ],
      "satisfaction_rating": null,
      "sharing_agreement_ids": [],
      "custom_status_id": 1234,
      "fields": [
        {
          "id": 360001,
          "value": "acme.io"
        },
        {
          "id": 360002,
          "value": "growth"
        },
        {
          "id": 360003,
          "value": "browser_error"
        }
      ],
      "followup_ids": [],
      "ticket_form_id": 60001,
      "brand_id": 70001,
      "allow_channelback": false,
      "allow_attachments": true,
      "from_messaging_channel": false,
      "via": {
        "channel": "web",
        "source": {
          "from": {
            "address": "jane@acme.io",
            "name": "Jane Smith"
          },
          "to": {
            "name": "Acme Support",
            "address": "support@acme.io"
          },
          "rel": null
        }
      },
      "created_at": "2026-07-10T14:30:00Z",
      "updated_at": "2026-07-11T09:15:00Z"
    },
    {
      "id": 1002,
      "url": "https://acme.zendesk.com/api/v2/tickets/1002.json",
      "external_id": null,
      "type": "question",
      "subject": "How to export data?",
      "raw_subject": "How to export data?",
      "description": "Can you help me understand how to export my account data to CSV?",
      "priority": "normal",
      "status": "pending",
      "recipient": "support@acme.io",
      "requester_id": 20002,
      "submitter_id": 20002,
      "assignee_id": 30001,
      "organization_id": 40002,
      "group_id": 50001,
      "collaborator_ids": [],
      "follower_ids": [],
      "email_cc_ids": [],
      "forum_topic_id": null,
      "problem_id": null,
      "has_incidents": false,
      "is_public": true,
      "due_at": null,
      "tags": ["data-export", "how-to"],
      "custom_fields": [
        {
          "id": 360001,
          "value": "globex.com"
        },
        {
          "id": 360002,
          "value": "professional"
        }
      ],
      "satisfaction_rating": null,
      "sharing_agreement_ids": [],
      "custom_status_id": 1235,
      "fields": [
        {
          "id": 360001,
          "value": "globex.com"
        },
        {
          "id": 360002,
          "value": "professional"
        }
      ],
      "followup_ids": [],
      "ticket_form_id": 60001,
      "brand_id": 70001,
      "allow_channelback": false,
      "allow_attachments": true,
      "from_messaging_channel": false,
      "via": {
        "channel": "email",
        "source": {
          "from": {
            "address": "bob@globex.com",
            "name": "Bob Johnson"
          },
          "to": {
            "name": "Acme Support",
            "address": "support@acme.io"
          },
          "rel": null
        }
      },
      "created_at": "2026-07-12T08:00:00Z",
      "updated_at": "2026-07-12T10:30:00Z"
    }
  ],
  "meta": {
    "has_more": true,
    "after_cursor": "eyJvIjoiLXVwZGF0ZWRfYXQiLCJ2IjoiMjAyNi0wNy0xMlQxMDozMDowMFoifQ==",
    "before_cursor": "eyJvIjoiLXVwZGF0ZWRfYXQiLCJ2IjoiMjAyNi0wNy0xMFQxNDozMDowMFoifQ=="
  },
  "links": {
    "prev": "https://acme.zendesk.com/api/v2/tickets.json?page[before]=eyJv...",
    "next": "https://acme.zendesk.com/api/v2/tickets.json?page[after]=eyJv..."
  },
  "count": 48
}
```

---

### GET /users.json

List users (end-users, agents, admins).

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page[size]` | int | 100 | Items per page (max 100) |
| `page[after]` | string | — | Cursor from `meta.after_cursor` |
| `role` | string | — | Filter: `end-user`, `agent`, `admin` |

**Example Request:**

```bash
curl -u "admin@acme.io/token:zd_api_token_mock_xxxxxxxxxxxx" \
  "https://acme.zendesk.com/api/v2/users.json?role=end-user&page[size]=2"
```

**Example Response:**

```json
{
  "users": [
    {
      "id": 20001,
      "url": "https://acme.zendesk.com/api/v2/users/20001.json",
      "name": "Jane Smith",
      "email": "jane@acme.io",
      "created_at": "2025-03-15T10:30:00Z",
      "updated_at": "2026-07-14T18:45:00Z",
      "time_zone": "Pacific Time (US & Canada)",
      "iana_time_zone": "America/Los_Angeles",
      "phone": "+14155551234",
      "shared_phone_number": false,
      "photo": null,
      "locale_id": 1,
      "locale": "en-US",
      "organization_id": 40001,
      "role": "end-user",
      "verified": true,
      "external_id": "user_jane_acme",
      "tags": ["vip", "billing-contact"],
      "alias": null,
      "active": true,
      "shared": false,
      "shared_agent": false,
      "last_login_at": "2026-07-14T18:45:00Z",
      "two_factor_auth_enabled": false,
      "signature": null,
      "details": "Primary contact at Acme Corp",
      "notes": "VIP customer on Growth plan",
      "role_type": null,
      "custom_role_id": null,
      "moderator": false,
      "ticket_restriction": "requested",
      "only_private_comments": false,
      "restricted_agent": false,
      "suspended": false,
      "default_group_id": null,
      "report_csv": false,
      "user_fields": {
        "company_domain": "acme.io",
        "plan": "growth",
        "mrr": 4800
      }
    }
  ],
  "meta": {
    "has_more": true,
    "after_cursor": "eyJvIjoiLW5hbWUiLCJ2IjoiSmFuZSBTbWl0aCJ9",
    "before_cursor": null
  },
  "links": {
    "prev": null,
    "next": "https://acme.zendesk.com/api/v2/users.json?page[after]=eyJv..."
  },
  "count": 25
}
```

---

### GET /organizations.json

List organizations.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page[size]` | int | 100 | Items per page (max 100) |
| `page[after]` | string | — | Cursor from `meta.after_cursor` |

**Example Request:**

```bash
curl -u "admin@acme.io/token:zd_api_token_mock_xxxxxxxxxxxx" \
  "https://acme.zendesk.com/api/v2/organizations.json?page[size]=2"
```

**Example Response:**

```json
{
  "organizations": [
    {
      "id": 40001,
      "url": "https://acme.zendesk.com/api/v2/organizations/40001.json",
      "name": "Acme Corp",
      "shared_tickets": false,
      "shared_comments": false,
      "external_id": "acme_io",
      "created_at": "2025-03-15T10:00:00Z",
      "updated_at": "2026-07-10T14:00:00Z",
      "domain_names": ["acme.io", "acme.com"],
      "details": "Technology company, Growth plan",
      "notes": "VIP account — escalate billing issues",
      "group_id": null,
      "tags": ["enterprise", "vip"],
      "organization_fields": {
        "plan": "growth",
        "mrr": 4800,
        "industry": "Technology",
        "employee_count": 150,
        "health_score": 85
      }
    },
    {
      "id": 40002,
      "url": "https://acme.zendesk.com/api/v2/organizations/40002.json",
      "name": "Globex Inc",
      "shared_tickets": false,
      "shared_comments": false,
      "external_id": "globex_com",
      "created_at": "2025-06-20T14:00:00Z",
      "updated_at": "2026-07-12T08:00:00Z",
      "domain_names": ["globex.com"],
      "details": "Manufacturing company",
      "notes": "",
      "group_id": null,
      "tags": ["standard"],
      "organization_fields": {
        "plan": "professional",
        "mrr": 2400,
        "industry": "Manufacturing",
        "employee_count": 500,
        "health_score": 72
      }
    }
  ],
  "meta": {
    "has_more": false,
    "after_cursor": "eyJvIjoiLW5hbWUiLCJ2IjoiR2xvYmV4IEluYyJ9",
    "before_cursor": "eyJvIjoiLW5hbWUiLCJ2IjoiQWNtZSBDb3JwIn0="
  },
  "links": {
    "prev": "https://acme.zendesk.com/api/v2/organizations.json?page[before]=eyJv...",
    "next": null
  },
  "count": 10
}
```

---

### GET /search.json

Search across tickets, users, and organizations.

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | Yes | Search query (Zendesk search syntax) |
| `page[size]` | int | — | Items per page (max 100) |
| `page[after]` | string | — | Cursor |

**Example Request:**

```bash
curl -u "admin@acme.io/token:zd_api_token_mock_xxxxxxxxxxxx" \
  "https://acme.zendesk.com/api/v2/search.json?query=type:ticket%20status:open"
```

**Example Response:**

```json
{
  "results": [
    {
      "id": 1001,
      "result_type": "ticket",
      "url": "https://acme.zendesk.com/api/v2/tickets/1001.json",
      "subject": "Cannot access billing dashboard",
      "description": "Hi, I'm unable to access the billing section...",
      "status": "open",
      "priority": "high",
      "requester_id": 20001,
      "assignee_id": 30001,
      "organization_id": 40001,
      "created_at": "2026-07-10T14:30:00Z",
      "updated_at": "2026-07-11T09:15:00Z",
      "via": {
        "channel": "web"
      }
    }
  ],
  "facets": null,
  "count": 12,
  "next_page": null,
  "previous_page": null
}
```

---

## Pagination

Zendesk uses **cursor-based pagination** (CBP) on all list endpoints.

### How It Works

1. Set `page[size]` (default 100, max 100).
2. Response includes `meta.has_more` and `meta.after_cursor`.
3. Pass `page[after]` with the value from `meta.after_cursor` for the next page.
4. **Done** when `meta.has_more` is `false`.

### Example Pagination Flow

```bash
# Page 1
curl -u "admin:token:xxx" \
  "https://acme.zendesk.com/api/v2/tickets.json?page[size]=100"
# Response: meta.has_more = true, meta.after_cursor = "eyJv..."

# Page 2
curl -u "admin:token:xxx" \
  "https://acme.zendesk.com/api/v2/tickets.json?page[size]=100&page[after]=eyJv..."
# Response: meta.has_more = true, meta.after_cursor = "eyJx..."

# Page 3 (last)
curl -u "admin:token:xxx" \
  "https://acme.zendesk.com/api/v2/tickets.json?page[size]=100&page[after]=eyJx..."
# Response: meta.has_more = false → done
```

### Backward Pagination

Use `page[before]` with `meta.before_cursor` to go backwards. Both `links.prev` and `links.next` provide full URLs.

---

## Error Responses

### 401 Unauthorized

```json
{
  "error": "Couldn't authenticate you"
}
```

### 404 Not Found

```json
{
  "error": "RecordNotFound",
  "description": "Not found"
}
```

### 422 Unprocessable Entity

```json
{
  "error": "RecordInvalid",
  "description": "Record validation errors",
  "details": {
    "value": [
      {
        "type": "blank",
        "description": "can't be blank"
      }
    ]
  }
}
```

### 429 Too Many Requests

```json
{
  "error": "TooManyRequests",
  "description": "Rate limit exceeded. Try again in 30 seconds.",
  "retry_after": 30
}
```

Response includes `Retry-After` header (seconds).

---

## Rate Limits

| Plan | Limit |
|------|-------|
| Team | 200 requests/minute |
| Growth | 400 requests/minute |
| Professional | 400 requests/minute |
| Enterprise | 700 requests/minute |
| Enterprise Plus | 2,500 requests/minute |

Rate limit headers:
```
X-Rate-Limit: 700
X-Rate-Limit-Remaining: 695
Retry-After: 30
```

---

## Notes

- The Basic Auth format is `{email}/token:{api_token}` — note the `/token` literal between the email and API token.
- All list endpoints wrap results in a named key (`tickets`, `users`, `organizations`), NOT a generic `data` key.
- Pagination metadata is in `meta` (with `has_more`, `after_cursor`, `before_cursor`) and `links` (with full URLs).
- `count` at the top level is the total count of matching records, not the count in the current page.
- `custom_fields` on tickets is an array of `{id, value}` pairs. Field IDs are numeric.
- `user_fields` and `organization_fields` are flat objects with field keys as strings.
- `via` on tickets describes the channel and source (web, email, api, chat, etc.).
- Timestamps are ISO 8601 UTC (always `Z` suffix).
- `tags` are flat string arrays, not objects.
- The search endpoint (`/search.json`) uses Zendesk's search syntax (e.g., `type:ticket status:open priority:high`).
- Ticket `status` values: `new`, `open`, `pending`, `hold`, `solved`, `closed`.
- Ticket `type` values: `problem`, `incident`, `question`, `task`.
- Ticket `priority` values: `urgent`, `high`, `normal`, `low`.
- The List Tickets endpoint does not support direct status filtering; use `/search.json` with `type:ticket status:{value}` to filter tickets by status.

---

## Reference

- [Tickets](https://developer.zendesk.com/api-reference/ticketing/tickets/tickets/)
- [Users](https://developer.zendesk.com/api-reference/ticketing/users/users/)
- [Organizations](https://developer.zendesk.com/api-reference/ticketing/organizations/organizations/)
- [Search](https://developer.zendesk.com/api-reference/ticketing/ticket-management/search/)
- [Pagination](https://developer.zendesk.com/api-reference/introduction/pagination/)
- [Rate limits](https://developer.zendesk.com/api-reference/introduction/rate-limits/)
- [Cursor pagination guide](https://developer.zendesk.com/documentation/api-basics/pagination/paginating-through-lists-using-cursor-pagination/)
