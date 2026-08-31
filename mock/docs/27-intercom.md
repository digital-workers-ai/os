# Intercom API

> API Version: 2.15
> Category: Support / Customer Engagement

---

## Base URL

```
https://api.intercom.io
```

## Authentication

Bearer token (access token from Intercom app settings or OAuth):

```
Authorization: Bearer int_mock_xxxxxxxxxxxx
Content-Type: application/json
Accept: application/json
Intercom-Version: 2.15
```

The `Intercom-Version` header pins the API version. Returns `401 Unauthorized` without valid token.

---

## Endpoints

### GET /contacts

List all contacts (users and leads).

**Query Parameters:**

None — use POST /contacts/search for filtering.

For cursor pagination on the list endpoint, pass `starting_after` from the previous response.

**Example Request:**

```bash
curl -H "Authorization: Bearer int_mock_xxxxxxxxxxxx" \
  -H "Intercom-Version: 2.15" \
  "https://api.intercom.io/contacts"
```

**Example Response:**

```json
{
  "type": "list",
  "data": [
    {
      "type": "contact",
      "id": "con_abc123",
      "workspace_id": "ws_mock_001",
      "external_id": "user_jane_acme",
      "role": "user",
      "email": "jane@acme.io",
      "phone": "+14155551234",
      "name": "Jane Smith",
      "avatar": null,
      "owner_id": null,
      "social_profiles": {
        "type": "list",
        "data": []
      },
      "has_hard_bounced": false,
      "marked_email_as_spam": false,
      "unsubscribed_from_emails": false,
      "created_at": 1710500000,
      "updated_at": 1719835200,
      "signed_up_at": 1710500000,
      "last_seen_at": 1720454400,
      "last_replied_at": 1720368000,
      "last_contacted_at": 1720281600,
      "last_email_opened_at": 1720195200,
      "last_email_clicked_at": 1720108800,
      "language_override": null,
      "browser": "Chrome",
      "browser_version": "126.0.0",
      "browser_language": "en-US",
      "os": "Mac OS X 14.5",
      "location": {
        "type": "location",
        "country": "United States",
        "region": "California",
        "city": "San Francisco",
        "country_code": "US",
        "continent_code": "NA"
      },
      "android_app_name": null,
      "android_app_version": null,
      "android_device": null,
      "android_os_version": null,
      "android_sdk_version": null,
      "android_last_seen_at": null,
      "ios_app_name": null,
      "ios_app_version": null,
      "ios_device": null,
      "ios_os_version": null,
      "ios_sdk_version": null,
      "ios_last_seen_at": null,
      "custom_attributes": {
        "company": "Acme Corp",
        "plan": "growth",
        "mrr": 4800,
        "signup_source": "organic",
        "company_domain": "acme.io"
      },
      "tags": {
        "type": "list",
        "data": [
          {
            "type": "tag",
            "id": "tag_001",
            "name": "vip"
          }
        ],
        "url": "/contacts/con_abc123/tags",
        "total_count": 1,
        "has_more": false
      },
      "notes": {
        "type": "list",
        "data": [],
        "url": "/contacts/con_abc123/notes",
        "total_count": 0,
        "has_more": false
      },
      "companies": {
        "type": "list",
        "data": [
          {
            "type": "company",
            "id": "comp_acme001",
            "name": "Acme Corp",
            "company_id": "acme_io"
          }
        ],
        "url": "/contacts/con_abc123/companies",
        "total_count": 1,
        "has_more": false
      }
    }
  ],
  "total_count": 25,
  "pages": {
    "type": "pages",
    "next": {
      "page": 2,
      "starting_after": "con_def456"
    },
    "page": 1,
    "per_page": 50,
    "total_pages": 1
  }
}
```

---

### GET /conversations

List conversations.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `starting_after` | string | — | Cursor from `pages.next.starting_after` |
| `per_page` | int | 20 | Items per page (max 150) |

**Example Request:**

```bash
curl -H "Authorization: Bearer int_mock_xxxxxxxxxxxx" \
  -H "Intercom-Version: 2.15" \
  "https://api.intercom.io/conversations?per_page=2"
```

**Example Response:**

```json
{
  "type": "conversation.list",
  "conversations": [
    {
      "type": "conversation",
      "id": "conv_001",
      "created_at": 1720108800,
      "updated_at": 1720368000,
      "waiting_since": null,
      "snoozed_until": null,
      "title": "Issue with billing",
      "state": "open",
      "open": true,
      "read": true,
      "priority": "priority",
      "admin_assignee_id": 12345,
      "team_assignee_id": null,
      "source": {
        "type": "conversation",
        "id": "conv_001",
        "delivered_as": "customer_initiated",
        "subject": "",
        "body": "<p>Hi, I'm having issues with my latest invoice. Can you help?</p>",
        "author": {
          "type": "user",
          "id": "con_abc123",
          "name": "Jane Smith",
          "email": "jane@acme.io"
        },
        "attachments": [],
        "url": null
      },
      "contacts": {
        "type": "contact.list",
        "contacts": [
          {
            "type": "contact",
            "id": "con_abc123",
            "external_id": "user_jane_acme"
          }
        ]
      },
      "first_contact_reply": {
        "created_at": 1720108800,
        "type": "conversation",
        "url": null
      },
      "tags": {
        "type": "tag.list",
        "tags": [
          {
            "type": "tag",
            "id": "tag_billing",
            "name": "billing"
          }
        ]
      },
      "conversation_rating": null,
      "statistics": {
        "type": "conversation_statistics",
        "time_to_assignment": 120,
        "time_to_admin_reply": 300,
        "time_to_first_close": 7200,
        "time_to_last_close": 7200,
        "median_time_to_reply": 300,
        "first_contact_reply_at": 1720108800,
        "first_assignment_at": 1720108920,
        "first_admin_reply_at": 1720109100,
        "first_close_at": 1720116000,
        "last_assignment_at": 1720108920,
        "last_admin_reply_at": 1720109100,
        "last_close_at": 1720116000,
        "last_contact_reply_at": 1720108800,
        "count_reopens": 0,
        "count_assignments": 1,
        "count_conversation_parts": 4
      },
      "conversation_parts": {
        "type": "conversation_part.list",
        "conversation_parts": [
          {
            "type": "conversation_part",
            "id": "part_001",
            "part_type": "comment",
            "body": "<p>Sure, let me look into that for you.</p>",
            "created_at": 1720109100,
            "updated_at": 1720109100,
            "notified_at": 1720109100,
            "author": {
              "type": "admin",
              "id": "12345",
              "name": "Support Agent",
              "email": "support@os.dev"
            },
            "attachments": [],
            "external_id": null
          }
        ],
        "total_count": 4
      }
    }
  ],
  "total_count": 42,
  "pages": {
    "type": "pages",
    "next": {
      "page": 2,
      "starting_after": "conv_002"
    },
    "page": 1,
    "per_page": 2,
    "total_pages": 21
  }
}
```

---

### GET /companies

List companies.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | int | 1 | Page number |
| `per_page` | int | 15 | Items per page (max 60) |
| `order` | string | `desc` | `asc` or `desc` by `created_at` |

**Example Request:**

```bash
curl -H "Authorization: Bearer int_mock_xxxxxxxxxxxx" \
  -H "Intercom-Version: 2.15" \
  "https://api.intercom.io/companies?per_page=2"
```

**Example Response:**

```json
{
  "type": "list",
  "data": [
    {
      "type": "company",
      "id": "comp_acme001",
      "company_id": "acme_io",
      "name": "Acme Corp",
      "created_at": 1710500000,
      "updated_at": 1720454400,
      "remote_created_at": 1710500000,
      "last_request_at": 1720454400,
      "monthly_spend": 4800,
      "session_count": 342,
      "user_count": 3,
      "size": 150,
      "website": "https://acme.io",
      "industry": "Technology",
      "plan": {
        "type": "plan",
        "id": "plan_growth",
        "name": "Growth"
      },
      "segments": {
        "type": "segment.list",
        "segments": [
          {
            "type": "segment",
            "id": "seg_active",
            "name": "Active Companies"
          }
        ]
      },
      "tags": {
        "type": "tag.list",
        "tags": [
          {
            "type": "tag",
            "id": "tag_enterprise",
            "name": "enterprise"
          }
        ]
      },
      "custom_attributes": {
        "domain": "acme.io",
        "mrr": 4800,
        "arr": 57600,
        "health_score": 85
      }
    }
  ],
  "total_count": 10,
  "pages": {
    "type": "pages",
    "next": {
      "page": 2,
      "starting_after": "comp_globex001"
    },
    "page": 1,
    "per_page": 2,
    "total_pages": 5
  }
}
```

---

### GET /contacts/{id}/notes

List notes for a contact.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `per_page` | int | 10 | Items per page |
| `page` | int | 1 | Page number |

**Example Request:**

```bash
curl -H "Authorization: Bearer int_mock_xxxxxxxxxxxx" \
  -H "Intercom-Version: 2.15" \
  "https://api.intercom.io/contacts/con_abc123/notes"
```

**Example Response:**

```json
{
  "type": "list",
  "data": [
    {
      "type": "note",
      "id": "note_001",
      "created_at": 1720195200,
      "body": "<p>VIP customer — escalate any billing issues directly to finance team.</p>",
      "author": {
        "type": "admin",
        "id": "12345",
        "name": "Support Agent",
        "email": "support@os.dev"
      },
      "contact": {
        "type": "contact",
        "id": "con_abc123"
      }
    }
  ],
  "total_count": 1,
  "pages": {
    "type": "pages",
    "page": 1,
    "per_page": 10,
    "total_pages": 1
  }
}
```

---

## Pagination

Intercom uses **cursor-based pagination** for contacts and conversations, and **page-based** for some endpoints.

### Cursor-Based (Contacts, Conversations)

1. Response includes `pages.next` with `starting_after` cursor.
2. Pass `starting_after` as query parameter on next request.
3. **Done** when `pages.next` is absent or null.

```bash
# Page 1
curl -H "Authorization: Bearer int_mock_xxxxxxxxxxxx" \
  "https://api.intercom.io/contacts?per_page=10"
# Response: pages.next.starting_after = "con_def456"

# Page 2
curl -H "Authorization: Bearer int_mock_xxxxxxxxxxxx" \
  "https://api.intercom.io/contacts?per_page=10&starting_after=con_def456"
# Response: pages.next = null → done
```

### Page-Based (Companies, Notes)

Some endpoints accept `page` as a query parameter. Check `pages.total_pages` to know when you're done.

---

## Error Responses

### 401 Unauthorized

```json
{
  "type": "error.list",
  "request_id": "req_abc123",
  "errors": [
    {
      "code": "unauthorized",
      "message": "Access Token Invalid"
    }
  ]
}
```

### 404 Not Found

```json
{
  "type": "error.list",
  "request_id": "req_def456",
  "errors": [
    {
      "code": "not_found",
      "message": "User Not Found"
    }
  ]
}
```

### 429 Too Many Requests

```json
{
  "type": "error.list",
  "request_id": "req_ghi789",
  "errors": [
    {
      "code": "rate_limit_exceeded",
      "message": "You have exceeded the rate limit. Please retry after 10 seconds."
    }
  ]
}
```

Response includes `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` headers.

---

## Rate Limits

| Scope | Limit |
|-------|-------|
| Per app | 10,000 requests/minute |
| Per workspace | 25,000 requests/minute |

The one-minute allowance is distributed across 10-second windows. Higher limits are available by contacting Intercom support.

Rate limit headers:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 995
X-RateLimit-Reset: 1720454460
```

---

## Notes

- All list responses have `type: "list"` or `type: "conversation.list"` at the top level.
- Timestamps are **Unix timestamps** (seconds), not ISO 8601.
- The `custom_attributes` object on contacts and companies holds arbitrary key-value data.
- Nested related resources (tags, companies, notes on a contact) include a mini-list with `total_count` and `has_more`.
- The `Intercom-Version` header is required and pins the API version. Without it, Intercom uses the app's default version.
- Errors are always wrapped in `{type: "error.list", errors: [...]}`.
- Conversation parts include the full conversation history (messages, notes, assignments, state changes).

---

## Reference

- [Intercom REST API reference](https://developers.intercom.com/docs/references/rest-api/api.intercom.io)
- [Contacts](https://developers.intercom.com/docs/references/rest-api/api.intercom.io/contacts)
- [Conversations](https://developers.intercom.com/docs/references/rest-api/api.intercom.io/conversations)
- [Rate Limiting](https://developers.intercom.com/docs/references/rest-api/errors/rate-limiting)
- [Cursor Pagination](https://developers.intercom.com/docs/build-an-integration/learn-more/rest-apis/pagination-cursor)
