# Mailchimp Marketing API

## Overview

Mailchimp Marketing API v3.0 provides access to lists (audiences), campaigns, automations, reports, and subscriber management for email marketing.

## Base URL

```
https://{dc}.api.mailchimp.com/3.0
```

The `{dc}` (data center) is extracted from the API key suffix. E.g., API key `abc123-us21` → base URL `https://us21.api.mailchimp.com/3.0`.

## Authentication

Two methods supported:

### Basic Auth (API Key)
```
Authorization: Basic {base64(anystring:API_KEY)}
```
Username can be any string; password is the full API key.

```bash
curl -u "anystring:mc_mock_apikey_us21" \
  https://us21.api.mailchimp.com/3.0/lists
```

### OAuth 2.0 Bearer
```
Authorization: Bearer {access_token}
```

Returns 401 without valid credentials:
```json
{
  "type": "https://mailchimp.com/developer/marketing/docs/errors/",
  "title": "API Key Invalid",
  "status": 401,
  "detail": "Your API key may be invalid, or you've attempted to access the wrong datacenter.",
  "instance": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

## Rate Limits

- **10 simultaneous connections** per API key
- **120-second timeout** per API call
- HTTP 429 when exceeded (use Batch endpoint for high-volume operations)
- Exceeding limits can result in API access being disabled

---

## Endpoints

### GET /3.0/lists

Returns all audiences (lists).

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `count` | int | 10 | Number of results (max 1000) |
| `offset` | int | 0 | Starting position |
| `fields` | string | — | Comma-separated fields to return |
| `exclude_fields` | string | — | Comma-separated fields to exclude |
| `sort_field` | string | — | `date_created` or `name` |
| `sort_dir` | string | `ASC` | `ASC` or `DESC` |

**Example Request:**
```bash
curl -u "anystring:mc_mock_apikey_us21" \
  "https://us21.api.mailchimp.com/3.0/lists?count=10&offset=0"
```

**Example Response:**
```json
{
  "lists": [
    {
      "id": "mc_list_acme_001",
      "web_id": 123456,
      "name": "Acme Corp Newsletter",
      "contact": {
        "company": "Acme Corp",
        "address1": "123 Main St",
        "city": "New York",
        "state": "NY",
        "zip": "10001",
        "country": "US"
      },
      "permission_reminder": "You signed up for updates on our website.",
      "use_archive_bar": true,
      "campaign_defaults": {
        "from_name": "Acme Corp",
        "from_email": "news@acme.io",
        "subject": "",
        "language": "en"
      },
      "notify_on_subscribe": "",
      "notify_on_unsubscribe": "",
      "date_created": "2025-03-15T10:30:00+00:00",
      "list_rating": 4,
      "email_type_option": false,
      "subscribe_url_short": "https://mailchi.mp/abc123/acme",
      "subscribe_url_long": "https://acme.us21.list-manage.com/subscribe?u=abc123&id=mc_list_acme_001",
      "beamer_address": "us21-abc123-1@inbound.mailchimp.com",
      "visibility": "pub",
      "double_optin": false,
      "has_welcome": true,
      "marketing_permissions": false,
      "stats": {
        "member_count": 15420,
        "unsubscribe_count": 342,
        "cleaned_count": 89,
        "member_count_since_send": 1250,
        "unsubscribe_count_since_send": 18,
        "cleaned_count_since_send": 3,
        "campaign_count": 45,
        "campaign_last_sent": "2026-07-10T14:00:00+00:00",
        "merge_field_count": 6,
        "avg_sub_rate": 120,
        "avg_unsub_rate": 5,
        "target_sub_rate": 40,
        "open_rate": 0.3245,
        "click_rate": 0.0856,
        "last_sub_date": "2026-07-14T09:15:00+00:00",
        "last_unsub_date": "2026-07-12T16:30:00+00:00"
      },
      "_links": [
        {
          "rel": "self",
          "href": "https://us21.api.mailchimp.com/3.0/lists/mc_list_acme_001",
          "method": "GET",
          "targetSchema": "https://us21.api.mailchimp.com/schema/3.0/Definitions/Lists/Response.json"
        },
        {
          "rel": "members",
          "href": "https://us21.api.mailchimp.com/3.0/lists/mc_list_acme_001/members",
          "method": "GET"
        }
      ]
    }
  ],
  "total_items": 1,
  "constraints": {
    "may_create": true,
    "max_instances": 500,
    "current_total_instances": 1
  },
  "_links": [
    {
      "rel": "self",
      "href": "https://us21.api.mailchimp.com/3.0/lists",
      "method": "GET"
    }
  ]
}
```

---

### GET /3.0/lists/{list_id}/members

Returns members (subscribers) of a list.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `count` | int | 10 | Results per page (max 1000) |
| `offset` | int | 0 | Starting position |
| `status` | string | — | `subscribed`, `unsubscribed`, `cleaned`, `pending`, `transactional` |
| `since_last_changed` | string | — | ISO 8601 date filter |
| `sort_field` | string | — | `timestamp_opt`, `last_changed` |
| `sort_dir` | string | `ASC` | `ASC` or `DESC` |

**Example Request:**
```bash
curl -u "anystring:mc_mock_apikey_us21" \
  "https://us21.api.mailchimp.com/3.0/lists/mc_list_acme_001/members?count=2&offset=0&status=subscribed"
```

**Example Response:**
```json
{
  "members": [
    {
      "id": "mc_member_jane_001",
      "email_address": "jane@acme.io",
      "unique_email_id": "ueid_jane_001",
      "contact_id": "mc_contact_jane_001",
      "full_name": "Jane Smith",
      "web_id": 789012,
      "email_type": "html",
      "status": "subscribed",
      "merge_fields": {
        "FNAME": "Jane",
        "LNAME": "Smith",
        "COMPANY": "Acme Corp",
        "PHONE": "+1-212-555-0100"
      },
      "stats": {
        "avg_open_rate": 0.42,
        "avg_click_rate": 0.12
      },
      "ip_signup": "192.168.1.100",
      "timestamp_signup": "2025-03-20T14:30:00+00:00",
      "ip_opt": "192.168.1.100",
      "timestamp_opt": "2025-03-20T14:30:00+00:00",
      "member_rating": 4,
      "last_changed": "2026-07-10T09:00:00+00:00",
      "language": "en",
      "vip": true,
      "email_client": "Gmail",
      "location": {
        "latitude": 40.7128,
        "longitude": -74.006,
        "gmtoff": -5,
        "dstoff": -4,
        "country_code": "US",
        "timezone": "America/New_York",
        "region": "NY"
      },
      "source": "Import",
      "tags_count": 3,
      "tags": [
        {"id": 101, "name": "Customer"},
        {"id": 102, "name": "Enterprise"},
        {"id": 103, "name": "Active"}
      ],
      "list_id": "mc_list_acme_001",
      "_links": [
        {
          "rel": "self",
          "href": "https://us21.api.mailchimp.com/3.0/lists/mc_list_acme_001/members/mc_member_jane_001",
          "method": "GET"
        }
      ]
    },
    {
      "id": "mc_member_bob_001",
      "email_address": "bob@soylent.co",
      "unique_email_id": "ueid_bob_001",
      "contact_id": "mc_contact_bob_001",
      "full_name": "Bob Smith",
      "web_id": 789013,
      "email_type": "html",
      "status": "subscribed",
      "merge_fields": {
        "FNAME": "Bob",
        "LNAME": "Smith",
        "COMPANY": "Soylent Corp",
        "PHONE": ""
      },
      "stats": {
        "avg_open_rate": 0.28,
        "avg_click_rate": 0.06
      },
      "ip_signup": "10.0.0.50",
      "timestamp_signup": "2025-06-10T09:00:00+00:00",
      "ip_opt": "10.0.0.50",
      "timestamp_opt": "2025-06-10T09:00:00+00:00",
      "member_rating": 3,
      "last_changed": "2026-06-15T12:00:00+00:00",
      "language": "en",
      "vip": false,
      "email_client": "Outlook",
      "location": {
        "latitude": 37.7749,
        "longitude": -122.4194,
        "gmtoff": -8,
        "dstoff": -7,
        "country_code": "US",
        "timezone": "America/Los_Angeles",
        "region": "CA"
      },
      "source": "API",
      "tags_count": 1,
      "tags": [
        {"id": 101, "name": "Customer"}
      ],
      "list_id": "mc_list_acme_001",
      "_links": [
        {
          "rel": "self",
          "href": "https://us21.api.mailchimp.com/3.0/lists/mc_list_acme_001/members/mc_member_bob_001",
          "method": "GET"
        }
      ]
    }
  ],
  "list_id": "mc_list_acme_001",
  "total_items": 15420,
  "_links": [
    {
      "rel": "self",
      "href": "https://us21.api.mailchimp.com/3.0/lists/mc_list_acme_001/members",
      "method": "GET"
    }
  ]
}
```

---

### GET /3.0/campaigns

Returns all campaigns.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `count` | int | 10 | Results per page (max 1000) |
| `offset` | int | 0 | Starting position |
| `type` | string | — | `regular`, `plaintext`, `absplit`, `rss`, `variate` |
| `status` | string | — | `save`, `paused`, `schedule`, `sending`, `sent` |
| `list_id` | string | — | Filter by audience |
| `since_send_time` | string | — | ISO 8601 date filter |
| `sort_field` | string | — | `create_time`, `send_time` |
| `sort_dir` | string | `DESC` | `ASC` or `DESC` |

**Example Request:**
```bash
curl -u "anystring:mc_mock_apikey_us21" \
  "https://us21.api.mailchimp.com/3.0/campaigns?count=2&status=sent"
```

**Example Response:**
```json
{
  "campaigns": [
    {
      "id": "mc_camp_welcome_001",
      "web_id": 456789,
      "type": "regular",
      "create_time": "2026-07-05T10:00:00+00:00",
      "archive_url": "https://mailchi.mp/abc123/welcome",
      "long_archive_url": "https://us21.campaign-archive.com/?u=abc&id=mc_camp_welcome_001",
      "status": "sent",
      "emails_sent": 1250,
      "send_time": "2026-07-10T14:00:00+00:00",
      "content_type": "template",
      "needs_block_refresh": false,
      "resendable": true,
      "recipients": {
        "list_id": "mc_list_acme_001",
        "list_is_active": true,
        "list_name": "Acme Corp Newsletter",
        "segment_text": "",
        "recipient_count": 1250
      },
      "settings": {
        "subject_line": "Welcome to Acme! Here's what you need to know",
        "preview_text": "Get started with your new account",
        "title": "Welcome Series - July 2026",
        "from_name": "Acme Corp",
        "reply_to": "support@acme.io",
        "use_conversation": false,
        "to_name": "*|FNAME|*",
        "folder_id": "",
        "authenticate": true,
        "auto_footer": true,
        "inline_css": false,
        "auto_tweet": false,
        "fb_comments": false,
        "timewarp": false,
        "template_id": 12345,
        "drag_and_drop": true
      },
      "tracking": {
        "opens": true,
        "html_clicks": true,
        "text_clicks": false,
        "goal_tracking": false,
        "ecomm360": false,
        "google_analytics": "acme_welcome_july2026",
        "clicktale": ""
      },
      "report_summary": {
        "opens": 580,
        "unique_opens": 456,
        "open_rate": 0.3648,
        "clicks": 185,
        "subscriber_clicks": 142,
        "click_rate": 0.1136,
        "ecommerce": {
          "total_orders": 0,
          "total_spent": 0,
          "total_revenue": 0
        }
      },
      "delivery_status": {
        "enabled": false
      },
      "_links": [
        {
          "rel": "self",
          "href": "https://us21.api.mailchimp.com/3.0/campaigns/mc_camp_welcome_001",
          "method": "GET"
        }
      ]
    }
  ],
  "total_items": 45,
  "_links": [
    {
      "rel": "self",
      "href": "https://us21.api.mailchimp.com/3.0/campaigns",
      "method": "GET"
    }
  ]
}
```

---

### GET /3.0/reports/{campaign_id}

Returns detailed report for a sent campaign.

**Example Request:**
```bash
curl -u "anystring:mc_mock_apikey_us21" \
  "https://us21.api.mailchimp.com/3.0/reports/mc_camp_welcome_001"
```

**Example Response:**
```json
{
  "id": "mc_camp_welcome_001",
  "campaign_title": "Welcome Series - July 2026",
  "type": "regular",
  "list_id": "mc_list_acme_001",
  "list_is_active": true,
  "list_name": "Acme Corp Newsletter",
  "subject_line": "Welcome to Acme! Here's what you need to know",
  "preview_text": "Get started with your new account",
  "emails_sent": 1250,
  "abuse_reports": 0,
  "unsubscribed": 8,
  "send_time": "2026-07-10T14:00:00+00:00",
  "bounces": {
    "hard_bounces": 3,
    "soft_bounces": 12,
    "syntax_errors": 0
  },
  "forwards": {
    "forwards_count": 5,
    "forwards_opens": 2
  },
  "opens": {
    "opens_total": 580,
    "unique_opens": 456,
    "open_rate": 0.3648,
    "last_open": "2026-07-14T22:15:00+00:00"
  },
  "clicks": {
    "clicks_total": 285,
    "unique_clicks": 142,
    "unique_subscriber_clicks": 142,
    "click_rate": 0.1136,
    "last_click": "2026-07-14T19:30:00+00:00"
  },
  "facebook_likes": {
    "recipient_likes": 0,
    "unique_likes": 0,
    "facebook_likes": 0
  },
  "industry_stats": {
    "type": "Technology and Computers",
    "open_rate": 0.22,
    "click_rate": 0.025,
    "bounce_rate": 0.008,
    "unopen_rate": 0.78,
    "unsub_rate": 0.002,
    "abuse_rate": 0.0001
  },
  "list_stats": {
    "sub_rate": 120.5,
    "unsub_rate": 5.2,
    "open_rate": 0.3245,
    "click_rate": 0.0856
  },
  "delivery_status": {
    "enabled": false
  },
  "_links": [
    {
      "rel": "self",
      "href": "https://us21.api.mailchimp.com/3.0/reports/mc_camp_welcome_001",
      "method": "GET"
    }
  ]
}
```

---

## Pagination

Offset-based using `offset` and `count` parameters.

```
GET /3.0/lists?count=10&offset=0     → items 0-9
GET /3.0/lists?count=10&offset=10    → items 10-19
GET /3.0/lists?count=10&offset=20    → items 20-29
```

- `count`: items per page (default 10, max 1000)
- `offset`: zero-based starting index
- `total_items` in response gives the total count
- Done when `offset + count >= total_items`
- Every response includes `_links` with HATEOAS navigation

## Error Responses

```json
{
  "type": "https://mailchimp.com/developer/marketing/docs/errors/",
  "title": "Resource Not Found",
  "status": 404,
  "detail": "The requested resource could not be found.",
  "instance": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

| HTTP Status | Title | Meaning |
|-------------|-------|---------|
| 400 | Bad Request | Malformed request body, invalid parameter, or validation error |
| 401 | API Key Invalid | Missing, invalid, or disabled API key |
| 403 | Forbidden | Insufficient permissions or deactivated account |
| 404 | Resource Not Found | Entity doesn't exist or incorrect path |
| 405 | Method Not Allowed | Endpoint doesn't support the HTTP method |
| 414 | Resource Nesting Too Deep | URL contains excessive path segments |
| 422 | InvalidMethodOverride | X-HTTP-Method-Override used with non-POST method |
| 429 | Too Many Requests | Exceeded 10 simultaneous connections or 500 pending batch webhooks |
| 500 | Internal Server Error | Server error |

## Notes

- Every response includes `_links` array for HATEOAS — follow links rather than constructing URLs
- The `{dc}` in the base URL is critical — API key `abc-us21` means data center `us21`
- Member IDs are MD5 hashes of lowercase email addresses
- `merge_fields` are custom fields configured per list (FNAME, LNAME are defaults)
- Campaign `status` lifecycle: `save` → `schedule` → `sending` → `sent`
- `member_rating` is 1-5 stars based on engagement
- Rates (open_rate, click_rate) are decimals, not percentages (0.3648 = 36.48%)
- `total_items` is always present in list responses for pagination math
- `fields` and `exclude_fields` are mutually exclusive; nested fields use dot notation (e.g., `lists.name`)
- DELETE requests return only headers without a JSON body
- Unsupported HTTP methods can use `X-HTTP-Method-Override` header with POST requests
- All requests must use HTTPS with TLS 1.2+ (HTTP returns 426)

## Reference

- [Mailchimp Marketing API Overview](https://mailchimp.com/developer/marketing/)
- [Fundamentals (Auth, Base URL, Rate Limits)](https://mailchimp.com/developer/marketing/docs/fundamentals/)
- [Methods and Parameters (Pagination, Query Params)](https://mailchimp.com/developer/marketing/docs/methods-parameters/)
- [Errors](https://mailchimp.com/developer/marketing/docs/errors/)
- [API Reference (All Endpoints)](https://mailchimp.com/developer/marketing/api/)
- [Quick Start Guide](https://mailchimp.com/developer/marketing/guides/quick-start/)
- [OAuth 2 Guide](https://mailchimp.com/developer/marketing/guides/access-user-data-oauth-2/)
