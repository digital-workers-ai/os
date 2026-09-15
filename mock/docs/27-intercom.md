# Intercom API

> API Version: 2.10
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
Intercom-Version: 2.10
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
  -H "Intercom-Version: 2.10" \
  "https://api.intercom.io/contacts"
```

**Example Response:**

```json
{
  "type": "list",
  "data": [
    {
      "type": "contact",
      "id": "con_p3",
      "workspace_id": "ws_mock_001",
      "external_id": "user_sarah_acme",
      "role": "user",
      "email": "sarah@acme.io",
      "phone": null,
      "name": "Sarah Johnson",
      "avatar": null,
      "owner_id": null,
      "social_profiles": {
        "type": "list",
        "data": []
      },
      "has_hard_bounced": false,
      "marked_email_as_spam": false,
      "unsubscribed_from_emails": false,
      "unsubscribed_from_sms": false,
      "sms_consent": false,
      "created_at": 1710672800,
      "updated_at": 1720454400,
      "signed_up_at": 1710672800,
      "last_seen_at": 1720454400,
      "last_replied_at": null,
      "last_contacted_at": null,
      "last_email_opened_at": null,
      "last_email_clicked_at": null,
      "language_override": null,
      "browser": null,
      "browser_version": null,
      "browser_language": null,
      "os": null,
      "referrer": null,
      "location": {
        "type": "location",
        "country": null,
        "region": null,
        "city": null,
        "country_code": null,
        "continent_code": null
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
      "utm_campaign": null,
      "utm_content": null,
      "utm_medium": null,
      "utm_source": null,
      "utm_term": null,
      "custom_attributes": {},
      "tags": {
        "type": "list",
        "data": [],
        "url": "/contacts/con_p3/tags",
        "total_count": 0,
        "has_more": false
      },
      "notes": {
        "type": "list",
        "data": [],
        "url": "/contacts/con_p3/notes",
        "total_count": 0,
        "has_more": false
      },
      "opted_in_subscription_types": {
        "type": "list",
        "data": [],
        "url": "/contacts/con_p3/subscriptions",
        "total_count": 0,
        "has_more": false
      },
      "opted_out_subscription_types": {
        "type": "list",
        "data": [],
        "url": "/contacts/con_p3/subscriptions",
        "total_count": 0,
        "has_more": false
      },
      "companies": {
        "type": "list",
        "data": [
          {
            "type": "company",
            "id": "comp_c1",
            "url": "/companies/comp_c1"
          }
        ],
        "url": "/contacts/con_p3/companies",
        "total_count": 1,
        "has_more": false
      }
    }
  ],
  "total_count": 22,
  "pages": {
    "type": "pages",
    "next": {
      "page": 2,
      "starting_after": "con_p4"
    },
    "page": 1,
    "per_page": 2,
    "total_pages": 11
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
  -H "Intercom-Version: 2.10" \
  "https://api.intercom.io/conversations?per_page=2"
```

**Example Response:**

Two conversations are shown rather than one page: `conv_t1`, Messenger-originated, from page 1, and `conv_t5`, email-originated, from a later page.

```json
{
  "type": "conversation.list",
  "conversations": [
    {
      "type": "conversation",
      "id": "conv_t1",
      "created_at": 1720108800,
      "updated_at": 1720368000,
      "waiting_since": null,
      "snoozed_until": null,
      "title": null,
      "state": "open",
      "open": true,
      "read": false,
      "priority": "priority",
      "admin_assignee_id": null,
      "team_assignee_id": null,
      "source": null,
      "contacts": {
        "type": "contact.list",
        "contacts": [
          {
            "type": "contact",
            "id": "con_p7",
            "external_id": "user_tom_initech"
          }
        ]
      },
      "teammates": {
        "type": "admin.list",
        "admins": []
      },
      "first_contact_reply": null,
      "conversation_rating": null,
      "sla_applied": null,
      "ticket": null,
      "tags": {
        "type": "tag.list",
        "tags": []
      },
      "topics": {
        "type": "topic.list",
        "topics": [],
        "total_count": 0
      },
      "linked_objects": {
        "type": "list",
        "data": [],
        "total_count": 0,
        "has_more": false
      },
      "custom_attributes": {
        "Auto-translated": false,
        "Copilot used": false,
        "Fin AI Agent: Image used in reply": false,
        "Fin AI Agent: Preview": false,
        "Fin awaiting teammate input": false,
        "Has attachments": false,
        "Imported via standalone": false,
        "SDR Success Counted": false
      },
      "statistics": {
        "type": "conversation_statistics",
        "time_to_assignment": null,
        "time_to_admin_reply": null,
        "time_to_first_close": null,
        "time_to_last_close": null,
        "median_time_to_reply": null,
        "first_contact_reply_at": null,
        "first_assignment_at": null,
        "first_admin_reply_at": null,
        "first_close_at": null,
        "last_assignment_at": null,
        "last_assignment_admin_reply_at": null,
        "last_admin_reply_at": null,
        "last_close_at": null,
        "last_closed_by_id": null,
        "last_contact_reply_at": null,
        "count_reopens": 0,
        "count_assignments": 0,
        "count_conversation_parts": 2
      }
    },
    {
      "type": "conversation",
      "id": "conv_t5",
      "created_at": 1720454400,
      "updated_at": 1720713600,
      "waiting_since": null,
      "snoozed_until": null,
      "title": "Payment method declined",
      "state": "open",
      "open": true,
      "read": true,
      "priority": "priority",
      "admin_assignee_id": 12345,
      "team_assignee_id": null,
      "source": {
        "type": "conversation",
        "id": "conv_t5",
        "delivered_as": "customer_initiated",
        "subject": "",
        "body": "<p>Payment method declined</p>",
        "author": {
          "type": "user",
          "id": "con_p18",
          "name": "Tony Stark",
          "email": "tony@stark.io"
        },
        "attachments": [],
        "url": null
      },
      "contacts": {
        "type": "contact.list",
        "contacts": [
          {
            "type": "contact",
            "id": "con_p18",
            "external_id": "user_tony_stark"
          }
        ]
      },
      "teammates": {
        "type": "admin.list",
        "admins": []
      },
      "first_contact_reply": {
        "created_at": 1720454400,
        "type": "conversation",
        "url": null
      },
      "conversation_rating": null,
      "sla_applied": null,
      "ticket": null,
      "tags": {
        "type": "tag.list",
        "tags": []
      },
      "topics": {
        "type": "topic.list",
        "topics": [],
        "total_count": 0
      },
      "linked_objects": {
        "type": "list",
        "data": [],
        "total_count": 0,
        "has_more": false
      },
      "custom_attributes": {
        "Auto-translated": false,
        "Copilot used": false,
        "Fin AI Agent: Image used in reply": false,
        "Fin AI Agent: Preview": false,
        "Fin awaiting teammate input": false,
        "Has attachments": false,
        "Imported via standalone": false,
        "SDR Success Counted": false
      },
      "statistics": {
        "type": "conversation_statistics",
        "time_to_assignment": 120,
        "time_to_admin_reply": 300,
        "time_to_first_close": 7200,
        "time_to_last_close": 7200,
        "median_time_to_reply": 300,
        "first_contact_reply_at": 1720454400,
        "first_assignment_at": 1720454520,
        "first_admin_reply_at": 1720454700,
        "first_close_at": 1720461600,
        "last_assignment_at": 1720454520,
        "last_assignment_admin_reply_at": 1720454700,
        "last_admin_reply_at": 1720454700,
        "last_close_at": 1720461600,
        "last_closed_by_id": 12345,
        "last_contact_reply_at": 1720454400,
        "count_reopens": 0,
        "count_assignments": 1,
        "count_conversation_parts": 4
      }
    }
  ],
  "total_count": 10,
  "pages": {
    "type": "pages",
    "next": {
      "page": 2,
      "starting_after": "conv_t2"
    },
    "page": 1,
    "per_page": 2,
    "total_pages": 5
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
  -H "Intercom-Version: 2.10" \
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
  -H "Intercom-Version: 2.10" \
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
- The `custom_attributes` object holds arbitrary key-value data. A live workspace returned `{}` on every contact and eight workspace booleans on a conversation (`Auto-translated`, `Copilot used`, the two `Fin AI Agent` keys, `Fin awaiting teammate input`, `Has attachments`, `Imported via standalone`, `SDR Success Counted`).
- Nested related resources on a contact (tags, notes, companies, both subscription-type lists) come back as a mini-list with `url`, `total_count` and `has_more`. The company mini-list carries `id`, `type` and `url` — not `name`, not `company_id`.
- A conversation opened from the Messenger has no `source` part, no `title`, no `first_contact_reply`, no `admin_assignee_id`, and null for every `statistics` duration. `source` is null rather than absent, so `source.author.email` is a path that does not exist on that conversation; the connector reads `_author_email`, which its extract hook fills from the source part when there is one and leaves null when there is not.
- `browser`, `browser_version`, `browser_language`, `os`, `referrer`, `avatar`, `owner_id`, `phone`, every `location` field, and every `utm_*`, `ios_*` and `android_*` field come back null until a workspace fills them. A live workspace returned null for all of them.
- `GET /conversations` does not return `conversation_parts`. Only `GET /conversations/{id}` carries the conversation history (messages, notes, assignments, state changes).
- The `Intercom-Version` header is required and pins the API version. Without it, Intercom uses the app's default version. The connector and this stand-in both send `2.10`, and a pull against the live API on 2026-09-14 was accepted at that version and returned the shapes above, so the pin still holds.
- Errors are always wrapped in `{type: "error.list", errors: [...]}`.

---

## Reference

- [Intercom REST API reference](https://developers.intercom.com/docs/references/rest-api/api.intercom.io)
- [Contacts](https://developers.intercom.com/docs/references/rest-api/api.intercom.io/contacts)
- [Conversations](https://developers.intercom.com/docs/references/rest-api/api.intercom.io/conversations)
- [Rate Limiting](https://developers.intercom.com/docs/references/rest-api/errors/rate-limiting)
- [Cursor Pagination](https://developers.intercom.com/docs/build-an-integration/learn-more/rest-apis/pagination-cursor)
