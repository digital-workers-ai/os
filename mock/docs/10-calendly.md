# Calendly API v2

## Overview

Calendly API for fetching scheduled events and invitee information. Used to track meetings, demos, and sales calls in the pipeline.

## Base URL

```
https://api.calendly.com
```

Mock server prefix: `/calendly`

## Authentication

Personal Access Token via Bearer header.

```
Authorization: Bearer {CALENDLY_PERSONAL_ACCESS_TOKEN}
Content-Type: application/json
```

Config key: `CALENDLY_PERSONAL_ACCESS_TOKEN`. Optionally `CALENDLY_USER_URI` (auto-resolved via `/users/me` if not set).

## Endpoints

### GET /users/me

Get the authenticated user's information. Used to resolve the user URI for subsequent requests.

**Response:**

```json
{
  "resource": {
    "uri": "https://api.calendly.com/users/abc123def456",
    "name": "Jane Smith",
    "slug": "jane-smith",
    "email": "jane@acme.io",
    "scheduling_url": "https://calendly.com/jane-smith",
    "timezone": "America/New_York",
    "avatar_url": "https://d3v0px0pttie1i.cloudfront.net/uploads/user/avatar/12345/avatar.png",
    "created_at": "2025-01-15T10:30:00.000000Z",
    "updated_at": "2026-06-01T14:22:00.000000Z",
    "current_organization": "https://api.calendly.com/organizations/org789"
  }
}
```

### GET /scheduled_events

List scheduled events for a user.

**Query parameters:**
- `user` — user URI from `/users/me` response. Either `user` or `organization` is required.
- `organization` — organization URI from `/users/me` response (`current_organization`). Requires admin/owner role. Either `user` or `organization` is required.
- `invitee_email` — filter by invitee email address
- `count` — items per page (default 20, max 100)
- `sort` — `start_time:asc` or `start_time:desc`
- `min_start_time` — ISO 8601 datetime filter (e.g., `2026-06-01T00:00:00Z`)
- `max_start_time` — ISO 8601 datetime filter
- `status` — `active` or `canceled`
- `page_token` — pagination token from previous response

**Example request:**

```
GET /calendly/scheduled_events?user=https://api.calendly.com/users/abc123def456&count=3&sort=start_time:asc&min_start_time=2026-06-01T00:00:00Z&max_start_time=2026-07-01T00:00:00Z
```

**Response:**

```json
{
  "collection": [
    {
      "uri": "https://api.calendly.com/scheduled_events/evt_001",
      "name": "30 Minute Demo",
      "status": "active",
      "start_time": "2026-06-05T14:00:00.000000Z",
      "end_time": "2026-06-05T14:30:00.000000Z",
      "event_type": "https://api.calendly.com/event_types/et_demo30",
      "location": {
        "type": "google_conference",
        "join_url": "https://meet.google.com/abc-defg-hij",
        "status": "pushed"
      },
      "invitees_counter": {
        "total": 1,
        "active": 1,
        "limit": 1
      },
      "created_at": "2026-06-03T09:15:00.000000Z",
      "updated_at": "2026-06-03T09:15:00.000000Z",
      "event_memberships": [
        {
          "user": "https://api.calendly.com/users/abc123def456",
          "user_email": "jane@acme.io",
          "user_name": "Jane Smith"
        }
      ],
      "calendar_event": {
        "kind": "google",
        "external_id": "google_cal_abc123"
      }
    },
    {
      "uri": "https://api.calendly.com/scheduled_events/evt_002",
      "name": "Discovery Call",
      "status": "active",
      "start_time": "2026-06-10T16:00:00.000000Z",
      "end_time": "2026-06-10T16:45:00.000000Z",
      "event_type": "https://api.calendly.com/event_types/et_discovery",
      "location": {
        "type": "zoom",
        "join_url": "https://zoom.us/j/123456789",
        "status": "pushed"
      },
      "invitees_counter": {
        "total": 2,
        "active": 2,
        "limit": 5
      },
      "created_at": "2026-06-08T11:30:00.000000Z",
      "updated_at": "2026-06-08T11:30:00.000000Z",
      "event_memberships": [
        {
          "user": "https://api.calendly.com/users/abc123def456",
          "user_email": "jane@acme.io",
          "user_name": "Jane Smith"
        }
      ],
      "calendar_event": {
        "kind": "google",
        "external_id": "google_cal_def456"
      }
    },
    {
      "uri": "https://api.calendly.com/scheduled_events/evt_003",
      "name": "30 Minute Demo",
      "status": "canceled",
      "start_time": "2026-06-15T10:00:00.000000Z",
      "end_time": "2026-06-15T10:30:00.000000Z",
      "event_type": "https://api.calendly.com/event_types/et_demo30",
      "location": {
        "type": "google_conference",
        "join_url": "https://meet.google.com/xyz-uvwx-rst",
        "status": "pushed"
      },
      "invitees_counter": {
        "total": 1,
        "active": 0,
        "limit": 1
      },
      "created_at": "2026-06-12T08:45:00.000000Z",
      "updated_at": "2026-06-14T16:00:00.000000Z",
      "cancellation": {
        "canceled_by": "Invitee",
        "reason": "Schedule conflict"
      },
      "event_memberships": [
        {
          "user": "https://api.calendly.com/users/abc123def456",
          "user_email": "jane@acme.io",
          "user_name": "Jane Smith"
        }
      ],
      "calendar_event": {
        "kind": "google",
        "external_id": "google_cal_ghi789"
      }
    }
  ],
  "pagination": {
    "count": 3,
    "next_page": "https://api.calendly.com/scheduled_events?count=3&page_token=sEjwKmR2b3c",
    "next_page_token": "sEjwKmR2b3c",
    "previous_page": null,
    "previous_page_token": null
  }
}
```

### GET /scheduled_events/{event_uuid}/invitees

Get invitees for a specific event.

**Query parameters:**
- `count` — items per page (default 10)
- `page_token` — pagination token
- `status` — `active` or `canceled`

**Example request:**

```
GET /calendly/scheduled_events/evt_002/invitees?count=10
```

**Response:**

```json
{
  "collection": [
    {
      "uri": "https://api.calendly.com/scheduled_events/evt_002/invitees/inv_001",
      "email": "bob@globex.com",
      "name": "Bob Johnson",
      "first_name": "Bob",
      "last_name": "Johnson",
      "status": "active",
      "timezone": "America/Chicago",
      "created_at": "2026-06-08T11:30:00.000000Z",
      "updated_at": "2026-06-08T11:30:00.000000Z",
      "event": "https://api.calendly.com/scheduled_events/evt_002",
      "questions_and_answers": [
        {
          "question": "Company name",
          "answer": "Globex Inc",
          "position": 0
        },
        {
          "question": "What would you like to discuss?",
          "answer": "Interested in the Enterprise plan",
          "position": 1
        }
      ],
      "tracking": {
        "utm_campaign": "summer_promo",
        "utm_source": "linkedin",
        "utm_medium": "paid_social",
        "utm_term": null,
        "utm_content": null,
        "salesforce_uuid": null
      },
      "text_reminder_number": null,
      "rescheduled": false,
      "routing_form_submission": null,
      "payment": null,
      "no_show": null
    },
    {
      "uri": "https://api.calendly.com/scheduled_events/evt_002/invitees/inv_002",
      "email": "alice@globex.com",
      "name": "Alice Martinez",
      "first_name": "Alice",
      "last_name": "Martinez",
      "status": "active",
      "timezone": "America/Chicago",
      "created_at": "2026-06-08T12:00:00.000000Z",
      "updated_at": "2026-06-08T12:00:00.000000Z",
      "event": "https://api.calendly.com/scheduled_events/evt_002",
      "questions_and_answers": [],
      "tracking": {
        "utm_campaign": null,
        "utm_source": null,
        "utm_medium": null,
        "utm_term": null,
        "utm_content": null,
        "salesforce_uuid": null
      },
      "text_reminder_number": null,
      "rescheduled": false,
      "routing_form_submission": null,
      "payment": null,
      "no_show": null
    }
  ],
  "pagination": {
    "count": 2,
    "next_page": null,
    "next_page_token": null,
    "previous_page": null,
    "previous_page_token": null
  }
}
```

## Pagination

- **Mechanism:** Token-based via `pagination.next_page_token`
- **Page size:** Set via `count` query parameter (default 20, max 100)
- **To get next page:** Pass `page_token={next_page_token}` as query parameter
- **Done when:** `pagination.next_page_token` is `null`
- **Safety cap:** Max 50 pages in a single paginated fetch

```
Page 1: GET /scheduled_events?count=20
         → pagination.next_page_token = "sEjwKmR2b3c"
Page 2: GET /scheduled_events?count=20&page_token=sEjwKmR2b3c
         → pagination.next_page_token = "kLpQxY8nF1a"
Page 3: GET /scheduled_events?count=20&page_token=kLpQxY8nF1a
         → pagination.next_page_token = null  (done)
```

## Error Responses

**401 Unauthorized:**
```json
{
  "title": "Unauthenticated",
  "message": "The access token is invalid"
}
```

**403 Forbidden:**
```json
{
  "title": "Permission Denied",
  "message": "You do not have permission to access this resource"
}
```

**404 Not found:**
```json
{
  "title": "Resource Not Found",
  "message": "The requested resource was not found"
}
```

**429 Rate limited:**
```json
{
  "title": "Rate Limit Exceeded",
  "message": "You have exceeded the rate limit. Please retry after 60 seconds."
}
```

## Notes

- All URIs in responses are full URLs (e.g., `https://api.calendly.com/users/abc123`) — use as-is for subsequent requests
- Event UUIDs can be extracted from the URI path: `https://api.calendly.com/scheduled_events/{uuid}`
- Timestamps are ISO 8601 with microsecond precision and Z suffix
- The `user` query parameter requires the full user URI, not just the ID
- Retry: 3 attempts, exponential backoff (2^attempt seconds), on 429/500/502/503

## Reference

- [Calendly API Reference](https://developer.calendly.com/api-docs/d7755e2f9e5fe-calendly-api) -- Full API reference
- [Get Current User](https://developer.calendly.com/api-docs/b3A6MTEzMDIyOQ-get-current-user) -- GET /users/me endpoint
- [Getting Started](https://developer.calendly.com/getting-started) -- Authentication and setup guide
- [How to find the organization or user URI](https://developer.calendly.com/how-to-find-the-organization-or-user-uri) -- Finding required URI parameters
