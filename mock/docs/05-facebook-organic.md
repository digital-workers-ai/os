# Facebook Page API (Organic)

## Overview

The Facebook Page API provides access to page insights, posts, comments, reactions, reviews, and engagement metrics. Part of the Meta Graph API. Used by OS for organic social media data.

- **Category:** Social Media (Organic)
- **Production Base URL:** `https://graph.facebook.com/v25.0`
- **Mock Base URL:** `http://localhost:8100/meta/v25.0`
- **API Version:** v25.0
- **Response Format:** JSON

## Authentication

Uses `access_token` query parameter, like all Meta Graph API endpoints. For page data, a **Page Access Token** is required (not a user token).

### Page Token Exchange

Exchange a user token for a page-specific token:

```
GET /v25.0/me/accounts?access_token={user_token}&fields=id,access_token&limit=100
```

**Example response (200):**

```json
{
  "data": [
    {
      "id": "page_123456",
      "access_token": "EAABsbCS1iHgBAyyyyyy...",
      "name": "My Business Page"
    },
    {
      "id": "page_789012",
      "access_token": "EAABsbCS1iHgBAzzzzzz...",
      "name": "My Other Page"
    }
  ]
}
```

Use the page-specific `access_token` for all subsequent page API calls.

### Mock Server Token

Any non-empty `access_token` query parameter is accepted.

---

## Endpoints

### 1. Page Insights (Daily Metrics)

```
GET /v25.0/{page_id}/insights
```

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `access_token` | string | **required** | Page access token |
| `metric` | string | **required** | Comma-separated metric names (max ~15 per request) |
| `period` | string | `"day"` | `"day"`, `"week"`, `"days_28"`, `"month"`, `"lifetime"`, `"total_over_range"` |
| `since` | integer | — | Unix timestamp for range start |
| `until` | integer | — | Unix timestamp for range end |

**Metric chunking:** Meta caps insight requests at ~15 metrics. The dashboard-dbb client fetches in chunks of 10 (`CHUNK = 10`).

**Example request:**

```bash
curl "https://graph.facebook.com/v25.0/page_123456/insights?\
access_token=EAABsbCS1iHgBAyyyyyy&\
metric=page_impressions,page_engaged_users,page_post_engagements,page_fan_adds&\
period=day&\
since=1719792000&\
until=1720396800"
```

**Example response (200):**

```json
{
  "data": [
    {
      "name": "page_impressions",
      "period": "day",
      "title": "Daily Total Impressions",
      "description": "Daily: The number of times any content from your Page or about your Page entered a person's screen.",
      "id": "page_123456/insights/page_impressions/day",
      "values": [
        {"value": 4523, "end_time": "2026-07-01T07:00:00+0000"},
        {"value": 5102, "end_time": "2026-07-02T07:00:00+0000"},
        {"value": 3891, "end_time": "2026-07-03T07:00:00+0000"},
        {"value": 4750, "end_time": "2026-07-04T07:00:00+0000"},
        {"value": 5320, "end_time": "2026-07-05T07:00:00+0000"},
        {"value": 4100, "end_time": "2026-07-06T07:00:00+0000"},
        {"value": 3980, "end_time": "2026-07-07T07:00:00+0000"}
      ]
    },
    {
      "name": "page_engaged_users",
      "period": "day",
      "title": "Daily Page Engaged Users",
      "description": "Daily: The number of people who engaged with your Page.",
      "id": "page_123456/insights/page_engaged_users/day",
      "values": [
        {"value": 312, "end_time": "2026-07-01T07:00:00+0000"},
        {"value": 428, "end_time": "2026-07-02T07:00:00+0000"},
        {"value": 275, "end_time": "2026-07-03T07:00:00+0000"},
        {"value": 350, "end_time": "2026-07-04T07:00:00+0000"},
        {"value": 490, "end_time": "2026-07-05T07:00:00+0000"},
        {"value": 290, "end_time": "2026-07-06T07:00:00+0000"},
        {"value": 265, "end_time": "2026-07-07T07:00:00+0000"}
      ]
    }
  ],
  "paging": {
    "previous": "https://graph.facebook.com/v25.0/page_123456/insights?...",
    "next": "https://graph.facebook.com/v25.0/page_123456/insights?..."
  }
}
```

### Common Page Metrics

| Metric | Description |
|--------|-------------|
| `page_impressions` | Total impressions |
| `page_impressions_unique` | Unique reach (**deprecated in v25.0+**) |
| `page_engaged_users` | People who engaged |
| `page_post_engagements` | Post engagement count |
| `page_fan_adds` | New page likes |
| `page_fan_removes` | Page unlikes |
| `page_views_total` | Total page views |
| `page_actions_post_reactions_total` | All reactions |
| `page_video_views` | Video views |

---

### 2. Page Node Fields

```
GET /v25.0/{page_id}
```

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `access_token` | string | **required** | Page access token |
| `fields` | string | — | Comma-separated field names |

**Example request:**

```bash
curl "https://graph.facebook.com/v25.0/page_123456?\
access_token=EAABsbCS1iHgBAyyyyyy&\
fields=followers_count,fan_count,rating_count,overall_star_rating,talking_about_count,were_here_count,checkins"
```

**Example response (200):**

```json
{
  "id": "page_123456",
  "followers_count": 24500,
  "fan_count": 23800,
  "rating_count": 142,
  "overall_star_rating": 4.6,
  "talking_about_count": 1250,
  "were_here_count": 890,
  "checkins": 890
}
```

---

### 3. Page Posts

```
GET /v25.0/{page_id}/posts
```

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `access_token` | string | **required** | Page access token |
| `fields` | string | — | `id,message,created_time,permalink_url,type,shares,likes.summary(true),comments.summary(true)` |
| `since` | integer | — | Unix timestamp filter |
| `limit` | integer | 25 | Results per page (max 100) |
| `after` | string | — | Pagination cursor |

**Example response (200):**

```json
{
  "data": [
    {
      "id": "page_123456_post_001",
      "message": "Excited to announce our new product launch! Check it out at the link below.",
      "created_time": "2026-07-05T14:30:00+0000",
      "permalink_url": "https://www.facebook.com/mybusiness/posts/post_001",
      "type": "link",
      "shares": {"count": 45},
      "likes": {
        "data": [],
        "summary": {"total_count": 312, "can_like": true, "has_liked": false}
      },
      "comments": {
        "data": [],
        "summary": {"total_count": 28, "can_comment": true}
      }
    },
    {
      "id": "page_123456_post_002",
      "message": "Behind the scenes with our team this week!",
      "created_time": "2026-07-03T10:00:00+0000",
      "permalink_url": "https://www.facebook.com/mybusiness/posts/post_002",
      "type": "photo",
      "shares": {"count": 12},
      "likes": {
        "data": [],
        "summary": {"total_count": 198, "can_like": true, "has_liked": false}
      },
      "comments": {
        "data": [],
        "summary": {"total_count": 15, "can_comment": true}
      }
    }
  ],
  "paging": {
    "cursors": {
      "before": "MAZDZD",
      "after": "MjQZD"
    },
    "next": "https://graph.facebook.com/v25.0/page_123456/posts?after=MjQZD&..."
  }
}
```

---

### 4. Post Insights

```
GET /v25.0/{post_id}/insights
```

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `access_token` | string | **required** | Page access token |
| `metric` | string | **required** | Comma-separated metric names (chunked in groups of 10) |

**Example response (200):**

```json
{
  "data": [
    {
      "name": "post_impressions",
      "period": "lifetime",
      "values": [{"value": 8542}],
      "title": "Lifetime Post Total Impressions",
      "id": "page_123456_post_001/insights/post_impressions/lifetime"
    },
    {
      "name": "post_engaged_users",
      "period": "lifetime",
      "values": [{"value": 423}],
      "title": "Lifetime Engaged Users",
      "id": "page_123456_post_001/insights/post_engaged_users/lifetime"
    },
    {
      "name": "post_clicks",
      "period": "lifetime",
      "values": [{"value": 312}],
      "title": "Lifetime Post Clicks",
      "id": "page_123456_post_001/insights/post_clicks/lifetime"
    }
  ]
}
```

Post insight metrics are chunked at `POST_CHUNK = 10` to avoid API errors.

---

### 5. Post Comments

```
GET /v25.0/{post_id}/comments
```

**Example response (200):**

```json
{
  "data": [
    {
      "id": "comment_001",
      "message": "This looks amazing! When is it available?",
      "created_time": "2026-07-05T15:12:00+0000",
      "from": {"name": "Jane Doe", "id": "user_456"}
    },
    {
      "id": "comment_002",
      "message": "Great work team!",
      "created_time": "2026-07-05T16:45:00+0000",
      "from": {"name": "Bob Smith", "id": "user_789"}
    }
  ],
  "paging": {
    "cursors": {"before": "MAZDZD", "after": "MjQZD"}
  }
}
```

---

### 6. Post Reactions

```
GET /v25.0/{post_id}/reactions
```

**Example response (200):**

```json
{
  "data": [
    {"id": "user_456", "name": "Jane Doe", "type": "LIKE"},
    {"id": "user_789", "name": "Bob Smith", "type": "LOVE"},
    {"id": "user_012", "name": "Alice Johnson", "type": "WOW"}
  ],
  "paging": {
    "cursors": {"before": "MAZDZD", "after": "MjQZD"},
    "next": "https://graph.facebook.com/v25.0/post_001/reactions?after=MjQZD&..."
  }
}
```

---

## Pagination

Same cursor-based pagination as Meta Ads. See `04-meta-ads.md` for full details.

### Edge Paginator (for posts, comments, reactions)

The dashboard-dbb client follows `paging.next` as a full URL with a cap of `max_pages = 20`.

### Insight Paginator

For page insights, the client follows `paging.next` as the full URL without adding params (they're embedded).

---

## Error Responses

Same error format as Meta Ads API. See `04-meta-ads.md`.

---

## Notes

- Page insights require a **Page Access Token** — user tokens won't work for page-level data
- Insight metrics are fetched in chunks of 10 due to Meta's ~15 metric limit per request
- The `/me/accounts` endpoint returns all pages the user has admin access to, with per-page access tokens
- Page node fields (`followers_count`, `fan_count`, etc.) are numeric values, not strings (unlike insight metrics)
- `since` on `/posts` is a Unix timestamp (integer), not an ISO date string
- Reactions types: LIKE, LOVE, WOW, HAHA, SAD, ANGRY, CARE
- Pagination caps at 20 pages in the dashboard-dbb client to prevent runaway fetches
- Page Insights data is only available on Pages with **100 or more likes**
- Maximum **90-day query window** when using `since`/`until` parameters; only the last **2 years** of insights data is available
- Several `_unique` metrics are deprecated in Graph API v25.0+, including `page_impressions_unique`, `page_video_views_unique`, `post_impressions_unique`, and related unique variants

---

## Reference

- [Page Insights API](https://developers.facebook.com/docs/platforminsights/page/) -- Overview of Page Insights, available metrics, and periods
- [Page/Insights Graph API Reference](https://developers.facebook.com/docs/graph-api/reference/page/insights/) -- Endpoint parameters, response structure, and deprecated metrics
- [Page Insights Reference](https://developers.facebook.com/docs/graph-api/reference/insights/) -- Full insights reference with metric catalog
- [Getting Started with Page Insights API](https://developers.facebook.com/blog/post/2022/11/08/getting-started-with-page-insights-api/) -- Tutorial and usage examples
