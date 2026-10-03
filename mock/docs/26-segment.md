# Segment Public API

> Category: CDP (Customer Data Platform)

---

## Base URL

```
https://api.segmentapis.com
```

## Authentication

Bearer token (API token from Segment workspace settings):

```
Authorization: Bearer sgp_mock_xxxxxxxxxxxx
Content-Type: application/json
```

Returns `401 Unauthorized` without valid token.

---

## Endpoints

### GET /sources

List all sources in the workspace.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `pagination.cursor` | string | — | Cursor for next page |
| `pagination.count` | int | 200 | Items per page (max 1000) |

**Example Request:**

```bash
curl -H "Authorization: Bearer sgp_mock_xxxxxxxxxxxx" \
  "https://api.segmentapis.com/sources?pagination.count=10"
```

**Example Response:**

```json
{
  "data": {
    "sources": [
      {
        "id": "src_abc123",
        "slug": "javascript",
        "name": "Production Website",
        "workspaceId": "ws_mock_001",
        "enabled": true,
        "writeKeys": ["wk_mock_xxxxxxxxxxxx"],
        "metadata": {
          "id": "javascript",
          "name": "Javascript",
          "slug": "javascript",
          "description": "Track events from your website",
          "logos": {
            "default": "https://cdn.filepicker.io/api/file/javascript.svg",
            "mark": "https://cdn.filepicker.io/api/file/javascript-mark.svg"
          },
          "options": [],
          "categories": ["Website"],
          "isCloudEventSource": false
        },
        "settings": {},
        "labels": [
          {
            "key": "environment",
            "value": "production"
          }
        ],
        "createdAt": "2025-01-15T10:00:00.000Z",
        "updatedAt": "2026-06-01T14:00:00.000Z"
      },
      {
        "id": "src_def456",
        "slug": "python",
        "name": "Backend Service",
        "workspaceId": "ws_mock_001",
        "enabled": true,
        "writeKeys": ["wk_mock_yyyyyyyyyyyy"],
        "metadata": {
          "id": "python",
          "name": "Python",
          "slug": "python",
          "description": "Track events from your Python server",
          "logos": {
            "default": "https://cdn.filepicker.io/api/file/python.svg",
            "mark": "https://cdn.filepicker.io/api/file/python-mark.svg"
          },
          "options": [],
          "categories": ["Server"],
          "isCloudEventSource": false
        },
        "settings": {},
        "labels": [
          {
            "key": "environment",
            "value": "production"
          }
        ],
        "createdAt": "2025-03-20T08:30:00.000Z",
        "updatedAt": "2026-05-15T11:00:00.000Z"
      }
    ],
    "pagination": {
      "current": "cursor_page1_abc",
      "next": "cursor_page2_def",
      "totalEntries": 5
    }
  }
}
```

---

### GET /destinations

List all destinations in the workspace.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `pagination.cursor` | string | — | Cursor for next page |
| `pagination.count` | int | 200 | Items per page (max 1000) |

**Example Request:**

```bash
curl -H "Authorization: Bearer sgp_mock_xxxxxxxxxxxx" \
  "https://api.segmentapis.com/destinations?pagination.count=10"
```

**Example Response:**

```json
{
  "data": {
    "destinations": [
      {
        "id": "dst_abc123",
        "name": "HubSpot Production",
        "enabled": true,
        "sourceId": "src_abc123",
        "metadata": {
          "id": "hubspot",
          "name": "HubSpot",
          "slug": "hubspot",
          "description": "Send data to HubSpot CRM",
          "logos": {
            "default": "https://cdn.filepicker.io/api/file/hubspot.svg"
          },
          "categories": ["CRM"],
          "website": "https://www.hubspot.com",
          "status": "PUBLIC"
        },
        "settings": {
          "apiKey": "****",
          "portalId": "12345678"
        },
        "createdAt": "2025-02-01T12:00:00.000Z",
        "updatedAt": "2026-06-01T14:00:00.000Z"
      },
      {
        "id": "dst_def456",
        "name": "Stripe Events",
        "enabled": true,
        "sourceId": "src_def456",
        "metadata": {
          "id": "stripe",
          "name": "Stripe",
          "slug": "stripe",
          "description": "Send data to Stripe",
          "logos": {
            "default": "https://cdn.filepicker.io/api/file/stripe.svg"
          },
          "categories": ["Payments"],
          "website": "https://stripe.com",
          "status": "PUBLIC"
        },
        "settings": {
          "apiKey": "****"
        },
        "createdAt": "2025-02-15T09:00:00.000Z",
        "updatedAt": "2026-06-01T14:00:00.000Z"
      }
    ],
    "pagination": {
      "current": "cursor_page1_abc",
      "next": "cursor_page2_def",
      "totalEntries": 8
    }
  }
}
```

---

### GET /spaces/{spaceId}/collections/{collectionId}/profiles

List user profiles in a Segment space (Unify / Personas).

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `pagination.cursor` | string | — | Cursor for next page |
| `pagination.count` | int | 200 | Items per page (max 1000) |
| `include` | string | — | Comma-separated: `traits`, `external_ids` |

**Example Request:**

```bash
curl -H "Authorization: Bearer sgp_mock_xxxxxxxxxxxx" \
  "https://api.segmentapis.com/spaces/spa_mock_001/collections/users/profiles?pagination.count=5&include=traits,external_ids"
```

**Example Response:**

```json
{
  "data": {
    "profiles": [
      {
        "segmentId": "seg_user_abc123",
        "traits": {
          "email": "jane@acme.io",
          "first_name": "Jane",
          "last_name": "Smith",
          "company": "Acme Corp",
          "plan": "growth",
          "created_at": "2025-03-15T10:30:00.000Z",
          "last_seen_at": "2026-07-14T18:45:00.000Z"
        },
        "external_ids": [
          {
            "id": "user_jane_acme",
            "type": "user_id",
            "collection": "users",
            "created_at": "2025-03-15T10:30:00.000Z",
            "encoding": "none"
          },
          {
            "id": "jane@acme.io",
            "type": "email",
            "collection": "users",
            "created_at": "2025-03-15T10:30:00.000Z",
            "encoding": "none"
          }
        ],
        "metadata": {
          "createdAt": "2025-03-15T10:30:00.000Z",
          "updatedAt": "2026-07-14T18:45:00.000Z"
        }
      },
      {
        "segmentId": "seg_user_def456",
        "traits": {
          "email": "bob@globex.com",
          "first_name": "Bob",
          "last_name": "Johnson",
          "company": "Globex Inc",
          "plan": "professional",
          "created_at": "2025-06-20T14:00:00.000Z",
          "last_seen_at": "2026-07-13T09:30:00.000Z"
        },
        "external_ids": [
          {
            "id": "user_bob_globex",
            "type": "user_id",
            "collection": "users",
            "created_at": "2025-06-20T14:00:00.000Z",
            "encoding": "none"
          },
          {
            "id": "bob@globex.com",
            "type": "email",
            "collection": "users",
            "created_at": "2025-06-20T14:00:00.000Z",
            "encoding": "none"
          }
        ],
        "metadata": {
          "createdAt": "2025-06-20T14:00:00.000Z",
          "updatedAt": "2026-07-13T09:30:00.000Z"
        }
      }
    ],
    "pagination": {
      "current": "cursor_page1_abc",
      "next": "cursor_page2_def",
      "totalEntries": 120
    }
  }
}
```

---

### GET /tracking-plans

List tracking plans.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `pagination.cursor` | string | — | Cursor for next page |
| `pagination.count` | int | 200 | Items per page (max 1000) |

**Example Request:**

```bash
curl -H "Authorization: Bearer sgp_mock_xxxxxxxxxxxx" \
  "https://api.segmentapis.com/tracking-plans"
```

**Example Response:**

```json
{
  "data": {
    "trackingPlans": [
      {
        "id": "tp_abc123",
        "name": "Production Tracking Plan",
        "slug": "production-tracking-plan",
        "description": "Events and properties for our production app",
        "type": "LIVE",
        "createdAt": "2025-01-10T09:00:00.000Z",
        "updatedAt": "2026-07-01T12:00:00.000Z"
      }
    ],
    "pagination": {
      "current": "cursor_page1_abc",
      "totalEntries": 1
    }
  }
}
```

---

## Pagination

Segment uses **cursor-based pagination** with a consistent pattern across all endpoints.

### How It Works

1. Set `pagination.count` for page size (default 200, max 1000).
2. Response includes `pagination.current`, `pagination.next`, `pagination.previous`, and `pagination.totalEntries`.
3. Pass `pagination.cursor` with the value from `pagination.next` for the next page.
4. **Done** when `pagination.next` is null.

### Example Pagination Flow

```bash
# Page 1
curl -H "Authorization: Bearer sgp_mock_xxxxxxxxxxxx" \
  "https://api.segmentapis.com/sources?pagination.count=10"
# Response: pagination.next = "cursor_page2_def"

# Page 2
curl -H "Authorization: Bearer sgp_mock_xxxxxxxxxxxx" \
  "https://api.segmentapis.com/sources?pagination.count=10&pagination.cursor=cursor_page2_def"
# Response: pagination.next = null → done
```

---

## Error Responses

### 401 Unauthorized

```json
{
  "errors": [
    {
      "type": "Unauthorized",
      "message": "Access token is missing or invalid",
      "status": 401
    }
  ]
}
```

### 404 Not Found

```json
{
  "errors": [
    {
      "type": "NotFound",
      "message": "Source 'src_notfound' not found",
      "status": 404
    }
  ]
}
```

### 429 Too Many Requests

```json
{
  "errors": [
    {
      "type": "TooManyRequests",
      "message": "Rate limit exceeded. Try again in 60 seconds.",
      "status": 429
    }
  ]
}
```

---

## Rate Limits

| API Type | Limit (approximate) |
|----------|-------|
| Config API (sources, destinations, etc.) | ~10 requests/second per workspace |
| Profiles API | ~100 requests/second per workspace |
| Tracking API | ~500 events/second per source |

Note: Segment uses dynamic rate limiting. The numbers above are observed approximations — official docs do not publish exact per-second limits.

---

## Notes

- All responses are wrapped in a `data` object at the top level.
- List endpoints nest the array under a named key within `data` (e.g., `data.sources`, `data.destinations`).
- Pagination is always at `data.pagination`, not top level.
- Timestamps are ISO 8601 with timezone (always `Z` / UTC).
- Sensitive settings values (API keys, secrets) are masked with `"****"` in responses.
- The Profiles API requires a Segment space (Unify/Personas) and is not available on all plans.

---

## Reference

- [Segment Public API Documentation](https://docs.segmentapis.com/)
- [Sources](https://docs.segmentapis.com/tag/Sources/)
- [Destinations](https://docs.segmentapis.com/tag/Destinations/)
- [Pagination](https://docs.segmentapis.com/tag/Pagination/)
- [Authentication](https://docs.segmentapis.com/tag/Authentication/)
- [Public API overview](https://segment.com/docs/api/public-api/)
