# Instagram Graph API (Organic)

## Overview

The Instagram Graph API provides access to business/creator account insights, media, demographics, and engagement data. Part of the Meta Graph API. Used by OS for organic Instagram analytics.

- **Category:** Social Media (Organic)
- **Production Base URL:** `https://graph.facebook.com/v25.0`
- **Mock Base URL:** `http://localhost:8100/meta/v25.0`
- **API Version:** v25.0
- **Response Format:** JSON

## Authentication

Uses `access_token` query parameter (same as all Meta Graph API endpoints).

```
?access_token=EAABsbCS1iHgBAxxxxxx
```

Requires a valid user or system user token. For the Instagram API with Facebook Login, the required permissions are `instagram_basic`, `instagram_manage_insights`, and `pages_read_engagement` (plus `ads_management` and `ads_read` if the user has a Page role via Business Manager). For the Instagram API with Instagram Login, the required permissions are `instagram_business_basic` and `instagram_business_manage_insights`. The Instagram Business Account ID is configured separately.

### Mock Server Token

Any non-empty `access_token` query parameter is accepted.

---

## Endpoints

### 1. Account Metadata

```
GET /v25.0/{ig_business_account_id}
```

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `access_token` | string | **required** | OAuth token |
| `fields` | string | — | `followers_count,media_count` |

**Example response (200):**

```json
{
  "id": "ig_12345",
  "followers_count": 15420,
  "media_count": 342
}
```

---

### 2. Account Insights (Daily Metrics)

```
GET /v25.0/{ig_business_account_id}/insights
```

Multiple query shapes depending on the metric type:

#### Daily Reach

| Parameter | Value |
|-----------|-------|
| `metric` | `reach` |
| `period` | `day` |
| `since` | Unix timestamp |
| `until` | Unix timestamp |

**Example response (200):**

```json
{
  "data": [
    {
      "name": "reach",
      "period": "day",
      "title": "Reach",
      "description": "The number of unique accounts that have seen any of your posts at least once.",
      "values": [
        {"value": 3421, "end_time": "2026-07-01T07:00:00+0000"},
        {"value": 4102, "end_time": "2026-07-02T07:00:00+0000"},
        {"value": 2891, "end_time": "2026-07-03T07:00:00+0000"}
      ],
      "id": "ig_12345/insights/reach/day"
    }
  ],
  "paging": {
    "previous": "https://graph.facebook.com/v25.0/ig_12345/insights?...",
    "next": "https://graph.facebook.com/v25.0/ig_12345/insights?..."
  }
}
```

#### Daily Total Value Metrics

| Parameter | Value |
|-----------|-------|
| `metric` | `accounts_engaged,total_interactions,likes,comments,shares,saves,replies` |
| `period` | `day` |
| `metric_type` | `total_value` |
| `since` | Unix timestamp (single day) |
| `until` | Unix timestamp (single day + 1) |

**Example response (200):**

```json
{
  "data": [
    {
      "name": "accounts_engaged",
      "period": "day",
      "total_value": {"value": 892},
      "title": "Accounts engaged",
      "id": "ig_12345/insights/accounts_engaged/day"
    },
    {
      "name": "total_interactions",
      "period": "day",
      "total_value": {"value": 1456},
      "title": "Total interactions",
      "id": "ig_12345/insights/total_interactions/day"
    },
    {
      "name": "likes",
      "period": "day",
      "total_value": {"value": 823},
      "title": "Likes",
      "id": "ig_12345/insights/likes/day"
    }
  ]
}
```

Note: `total_value` metrics are fetched **one day at a time** (since/until span a single day).

#### Follower Demographics

| Parameter | Value |
|-----------|-------|
| `metric` | `follower_demographics` |
| `period` | `lifetime` |
| `metric_type` | `total_value` |
| `breakdown` | `city`, `country`, `age`, or `gender` |

**Example response (200) — country breakdown:**

```json
{
  "data": [
    {
      "name": "follower_demographics",
      "period": "lifetime",
      "title": "Follower demographics",
      "total_value": {
        "breakdowns": [
          {
            "dimension_keys": ["timeframe", "country"],
            "results": [
              {"dimension_values": ["lifetime", "US"], "value": 5240},
              {"dimension_values": ["lifetime", "GB"], "value": 1820},
              {"dimension_values": ["lifetime", "CA"], "value": 1350},
              {"dimension_values": ["lifetime", "AU"], "value": 980},
              {"dimension_values": ["lifetime", "DE"], "value": 720}
            ]
          }
        ]
      },
      "id": "ig_12345/insights/follower_demographics/lifetime"
    }
  ]
}
```

**Example response (200) — age breakdown:**

```json
{
  "data": [
    {
      "name": "follower_demographics",
      "period": "lifetime",
      "title": "Follower demographics",
      "total_value": {
        "breakdowns": [
          {
            "dimension_keys": ["timeframe", "age"],
            "results": [
              {"dimension_values": ["lifetime", "18-24"], "value": 2150},
              {"dimension_values": ["lifetime", "25-34"], "value": 5420},
              {"dimension_values": ["lifetime", "35-44"], "value": 3890},
              {"dimension_values": ["lifetime", "45-54"], "value": 2100},
              {"dimension_values": ["lifetime", "55-64"], "value": 980},
              {"dimension_values": ["lifetime", "65+"], "value": 450}
            ]
          }
        ]
      },
      "id": "ig_12345/insights/follower_demographics/lifetime"
    }
  ]
}
```

#### Follower Count (Daily)

| Parameter | Value |
|-----------|-------|
| `metric` | `follower_count` |
| `period` | `day` |
| `since` | Unix timestamp |
| `until` | Unix timestamp |

**Example response (200):**

```json
{
  "data": [
    {
      "name": "follower_count",
      "period": "day",
      "values": [
        {"value": 15320, "end_time": "2026-07-01T07:00:00+0000"},
        {"value": 15355, "end_time": "2026-07-02T07:00:00+0000"},
        {"value": 15390, "end_time": "2026-07-03T07:00:00+0000"},
        {"value": 15420, "end_time": "2026-07-04T07:00:00+0000"}
      ],
      "id": "ig_12345/insights/follower_count/day"
    }
  ]
}
```

---

### 3. Media List

```
GET /v25.0/{ig_business_account_id}/media
```

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `access_token` | string | **required** | OAuth token |
| `fields` | string | — | `id,caption,timestamp,media_type,media_product_type,permalink,media_url,thumbnail_url` |
| `since` | integer | — | Unix timestamp filter |
| `limit` | integer | 25 | Results per page (max 100) |
| `after` | string | — | Pagination cursor |

**Example response (200):**

```json
{
  "data": [
    {
      "id": "media_001",
      "caption": "New product launch day! Link in bio for early access.",
      "timestamp": "2026-07-05T14:30:00+0000",
      "media_type": "CAROUSEL_ALBUM",
      "permalink": "https://www.instagram.com/p/abc123/",
      "media_url": "https://scontent.xx.fbcdn.net/v/...",
      "thumbnail_url": "https://scontent.xx.fbcdn.net/v/..."
    },
    {
      "id": "media_002",
      "caption": "Behind the scenes with the team! #startup #tech",
      "timestamp": "2026-07-03T10:00:00+0000",
      "media_type": "IMAGE",
      "permalink": "https://www.instagram.com/p/def456/",
      "media_url": "https://scontent.xx.fbcdn.net/v/..."
    },
    {
      "id": "media_003",
      "caption": "Quick tip: how to get started in 60 seconds",
      "timestamp": "2026-07-01T16:00:00+0000",
      "media_type": "VIDEO",
      "media_product_type": "REELS",
      "permalink": "https://www.instagram.com/reel/ghi789/",
      "thumbnail_url": "https://scontent.xx.fbcdn.net/v/..."
    }
  ],
  "paging": {
    "cursors": {
      "before": "MAZDZD",
      "after": "MjQZD"
    },
    "next": "https://graph.facebook.com/v25.0/ig_12345/media?after=MjQZD&..."
  }
}
```

### Media Types

The `media_type` field only returns three values. To distinguish reels/stories from regular content, use `media_product_type`.

| `media_type` | Description |
|------|-------------|
| `IMAGE` | Single image post |
| `VIDEO` | Video post (includes Reels) |
| `CAROUSEL_ALBUM` | Multi-image carousel |

| `media_product_type` | Description |
|------|-------------|
| `FEED` | Regular feed post |
| `REELS` | Reel/short video |
| `STORY` | Story (24-hour) |
| `AD` | Ad content |

---

### 4. Media Insights

```
GET /v25.0/{media_id}/insights
```

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `access_token` | string | **required** | OAuth token |
| `metric` | string | **required** | Comma-separated — different metrics for different media types |

#### Metrics by Media Type

| Media Type | Available Metrics |
|-----------|-------------------|
| FEED (IMAGE) | `reach,views,total_interactions,likes,comments,shares,saved,follows,profile_visits,reposts` (`impressions` deprecated for media created after July 2024) |
| CAROUSEL_ALBUM | Album-level insights are **not available** in current API; carousel children also do not support individual insights |
| REELS | `views,reach,total_interactions,likes,comments,shares,saved,reposts,ig_reels_avg_watch_time,ig_reels_video_view_total_time` |
| STORIES | `reach,views,replies,shares,follows,profile_visits,navigation,total_interactions,reposts` (`impressions` deprecated for media created after July 2024) |

**Example response (200) — image post:**

```json
{
  "data": [
    {"name": "views", "period": "lifetime", "values": [{"value": 8542}], "id": "media_001/insights/views/lifetime"},
    {"name": "reach", "period": "lifetime", "values": [{"value": 6230}], "id": "media_001/insights/reach/lifetime"},
    {"name": "total_interactions", "period": "lifetime", "values": [{"value": 423}], "id": "media_001/insights/total_interactions/lifetime"},
    {"name": "saved", "period": "lifetime", "values": [{"value": 87}], "id": "media_001/insights/saved/lifetime"},
    {"name": "likes", "period": "lifetime", "values": [{"value": 312}], "id": "media_001/insights/likes/lifetime"},
    {"name": "comments", "period": "lifetime", "values": [{"value": 28}], "id": "media_001/insights/comments/lifetime"},
    {"name": "shares", "period": "lifetime", "values": [{"value": 45}], "id": "media_001/insights/shares/lifetime"}
  ]
}
```

---

### 5. Tagged Media

```
GET /v25.0/{ig_business_account_id}/tags
```

**Example response (200):**

```json
{
  "data": [
    {
      "id": "tagged_001",
      "caption": "Love using @mybusiness for our workflow!",
      "timestamp": "2026-07-04T12:00:00+0000",
      "media_type": "IMAGE",
      "permalink": "https://www.instagram.com/p/xyz789/"
    }
  ],
  "paging": {
    "cursors": {"before": "MAZDZD", "after": "MjQZD"}
  }
}
```

---

### 6. Content Publishing Limit

```
GET /v25.0/{ig_business_account_id}?fields=content_publishing_limit
```

**Example response (200):**

```json
{
  "content_publishing_limit": {
    "quota_usage": 3,
    "config": {
      "quota_total": 25,
      "quota_duration": 86400
    }
  },
  "id": "ig_12345"
}
```

---

## Pagination

Same cursor-based pagination as all Meta Graph API endpoints. See `04-meta-ads.md`.

- Uses `paging.cursors.after` + `paging.next`
- Pass `after` as query parameter for next page
- Done when `paging.next` is absent

---

## Error Responses

Same error format as Meta Ads API. See `04-meta-ads.md`.

---

## Notes

- Instagram insight values are **integers** (unlike Meta Ads which returns strings)
- `total_value` metrics must be fetched one day at a time (since/until = single day span)
- Demographic breakdowns use the nested `breakdowns[].dimension_keys` / `results[].dimension_values` structure
- Different media types have different available metrics — requesting an unsupported metric for a media type returns an error
- `media_url` may be absent for some media types (Reels may only have `thumbnail_url`)
- Insight metrics are chunked in groups of 10 to avoid exceeding Meta's per-request metric limit
- Business Discovery API allows fetching competitor profiles: `GET /{ig_id}?fields=business_discovery.username(competitor){followers_count,media_count}`
- The `impressions` metric is **deprecated for v22.0+** (April 2025); use `views` instead, which supports `total_value` type with `follower_type` and `media_product_type` breakdowns
- The `engagement` metric is deprecated; use `total_interactions` instead
- Story metrics expire after 24 hours; stories with fewer than 5 viewers return error code 10
- Insights data may be delayed up to 48 hours
- Some metrics are not available on accounts with fewer than 100 followers

---

## Reference

- [Instagram Insights Overview](https://developers.facebook.com/docs/instagram-platform/insights/) -- Overview of Instagram insights, permissions, and available metrics
- [Instagram User Insights Reference](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/insights/) -- Account-level metrics, metric_type, breakdowns, and deprecated metrics
- [Instagram Media Insights Reference](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-media/insights/) -- Media-level metrics by type (FEED, REELS, STORIES, CAROUSEL_ALBUM)
- [Instagram API Updates (Dec 2025)](https://developers.facebook.com/blog/post/2025/12/03/instragram-api-updates/) -- Recent API changes for insights and content management
