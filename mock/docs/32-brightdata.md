# Bright Data Scraper API (LinkedIn Company Posts)

## Overview

Bright Data's Scraper API delivers scraped datasets asynchronously: trigger a
collection, poll its progress, download the snapshot. The estate reads one
dataset, LinkedIn posts (`gd_lyy3tktm25m4avu764`), in *discover by company
URL* mode: given a company page, it returns that company's most recent posts
with their engagement counters. Nothing else on this host is read.

## Base URL

```
https://api.brightdata.com
```

The stand-in mounts the same paths under `/brightdata`.

## Authentication

An account API token, sent as a bearer on every request.

```
Authorization: Bearer <token>
```

Auth failures are 401 with a **plain-text** body (`text/html; charset=utf-8`),
not JSON:

| Request | Body |
|---------|------|
| No `Authorization` header | `Credentials are missing` |
| `Bearer` with an empty or unrecognised token | `Auth method is not supported` |
| `Basic …` | `Basic auth is not allowed` |

The management-API docs describe `{"error": "User authentication is
required"}`; the API does not send it.

## Pricing and latency

Pay as you go is $1.5 per 1,000 records, charged on delivered records only
(an error record costs nothing); the free tier is 5,000 records a month with
no card. A pull of three companies at `limit_per_input: 50` is at most 150
records.

Observed on 2026-09-16: one company at `limit_per_input: 10` went from trigger
to `ready` in 37 s (`running` at 0 s and 16 s of polling, `ready` at 32 s,
`collection_duration: 36592`); the snapshot download took 0.9 s. A dead
company page was `ready` in 4 s.

---

## Endpoints

### POST /datasets/v3/trigger

Starts a collection. Everything about *what* to collect is in the query
string; the body is the list of inputs.

**Query Parameters:**
| Param | Value | Description |
|-------|-------|-------------|
| `dataset_id` | `gd_lyy3tktm25m4avu764` | LinkedIn posts. Unknown → 404 `dataset does not exist` |
| `type` | `discover_new` | Discovery mode. Other → 400 `{"validation_errors": ["\"type\" must be one of [discover_new, url_collection]"]}` |
| `discover_by` | `company_url` | Other → 400 `Incorrect discovery collector id Available types: url, profile_url, company_url`; missing → 400 `Incorrect discovery collector id discover_by is required` |
| `format` | `json` | Snapshot format |
| `include_errors` | `true` | Failed inputs come back as error records instead of vanishing |
| `limit_per_input` | int | Posts per company. The pull asks 50; captured with 10 |

**Body:** a JSON array of `{"url": "https://www.linkedin.com/company/<slug>"}`.
The docs show `{"input": [...]}`; the API accepts the bare array, that wrapper
and a single object alike.

**Example Request:**
```bash
curl -X POST "https://api.brightdata.com/datasets/v3/trigger?dataset_id=gd_lyy3tktm25m4avu764&type=discover_new&discover_by=company_url&format=json&include_errors=true&limit_per_input=10" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '[{"url": "https://www.linkedin.com/company/hubspot"}]'
```

**Example Response:**
```json
{"snapshot_id": "sd_mu3j5zf4i64vu5aoj"}
```

The id is `sd_` plus seventeen lowercase alphanumerics. A company that does
not exist is **not** refused here: the trigger accepts any URL and the failure
surfaces later as an error record.

**Body errors** (all 400):

| Body | Response |
|------|----------|
| `[]` | `No data to trigger` (plain text) |
| `[{"name": "hubspot"}]` | `{"error": "Invalid input provided", "code": "validation_error", "type": "validation", "line": "{\"name\":\"hubspot\"}", "index": 1, "errors": [["name", "This input should not contain a name field"], ["url", "Required field"]]}` |
| `hello` | `{"error": "Parser cannot parse input: expected a value", "code": "parse_error"}` |
| *(empty)* | `{"error": "Parser has expected a value", "code": "parse_error"}` |

### GET /datasets/v3/progress/{snapshot_id}

Polled until the snapshot leaves `running`. The docs list five statuses:
`starting`, `running`, `ready`, `failed`, `canceled`. Three were observed.

**`running`** — `running_time` is milliseconds and grows between polls
(12652, then 28325):
```json
{"status": "running", "snapshot_id": "sd_mu3j5zf4i64vu5aoj", "dataset_id": "gd_lyy3tktm25m4avu764", "running_time": 12652}
```

**`ready`** — counts and durations join the body:
```json
{"status": "ready", "snapshot_id": "sd_mu3j5zf4i64vu5aoj", "dataset_id": "gd_lyy3tktm25m4avu764", "records": 10, "errors": 0, "collection_duration": 36592, "avg_duration_per_input": 36592}
```

**`ready` with a failed input** — `error_codes` appears before the counts and
the input is tallied under `errors`:
```json
{"status": "ready", "snapshot_id": "sd_mu3jb0ym1pwuyaxk2e", "dataset_id": "gd_lyy3tktm25m4avu764", "error_codes": {"dead_page": 1}, "records": 0, "errors": 1, "collection_duration": 3616, "avg_duration_per_input": 3616}
```

**`canceled`** — after `POST /datasets/v3/snapshot/{id}/cancel` (which answers
200 `OK`):
```json
{"status": "canceled", "snapshot_id": "sd_mu3j6kd1irv81k75v", "dataset_id": "gd_lyy3tktm25m4avu764", "error_codes": {"aborted_page": 1}}
```

`failed` was not observed; the docs say it carries an `error_message` such as
"No data found in discovery", "Snapshot is empty" or "Failed to deliver
snapshot".

An unknown id answers 404 with the plain text `Snapshot does not exist`.

### GET /datasets/v3/snapshot/{snapshot_id}

**Query Parameters:**
| Param | Value | Description |
|-------|-------|-------------|
| `format` | `json` | One JSON array; `ndjson` and `csv` also exist |

Before the snapshot is ready, 202:
```json
{"status": "running", "message": "Snapshot is not ready yet, try again in 30s"}
```

Once ready, 200 with the array of records, in no particular order. Every post
record carries all forty keys: a field with nothing to say is `null`, never
absent. An input that failed is one record with four keys.

**Example Record** (real, trimmed — nine of ten comments and the signed image
tokens removed):
```json
{
  "url": "https://www.linkedin.com/posts/hubspot_fantasy-football-is-actually-just-pipeline-activity-7503504518433878017-WAjk",
  "id": "7503504518433878017",
  "user_id": "hubspot",
  "use_url": "https://www.linkedin.com/company/hubspot?trk=public_post_feed-actor-image",
  "title": "Fantasy football is actually just pipeline management | HubSpot | 26 comments",
  "headline": "Fantasy football is actually just pipeline management",
  "post_text": "Fantasy football is actually just pipeline management",
  "date_posted": "2026-09-09T17:28:05.539Z",
  "hashtags": null,
  "embedded_links": null,
  "images": null,
  "videos": null,
  "num_likes": 454,
  "num_comments": 26,
  "more_articles_by_user": null,
  "more_relevant_posts": null,
  "top_visible_comments": [
    {
      "use_url": "https://www.linkedin.com/company/hintro?trk=public_post_comment_actor-name",
      "user_id": "hintro",
      "user_name": "Hintro",
      "comment_date": "2026-09-14T03:38:43.168Z",
      "comment": "The waiver wire thread above is the whole game. People re-score their fantasy roster every week and let a real pipeline sit untouched for a quarter. The discipline exists, it just lives in the wrong tab.",
      "tagged_users": null,
      "num_reactions": 0,
      "user_title": null,
      "comment_images": null,
      "comment_id": "7505107739132739584",
      "comment_url": "https://www.linkedin.com/feed/update/urn:li:ugcPost:7503504518433878017?commentUrn=urn%3Ali%3Acomment%3A%28ugcPost%3A7503504518433878017%2C7505107739132739584%29"
    }
  ],
  "user_followers": 1747772,
  "user_posts": 0,
  "user_articles": 0,
  "post_type": "post",
  "account_type": "Organization",
  "post_text_html": "Fantasy football is actually just pipeline management",
  "repost": {
    "repost_hangtags": null,
    "repost_attachments": null,
    "tagged_users": null,
    "tagged_companies": null
  },
  "tagged_companies": [],
  "tagged_people": [],
  "user_title": null,
  "author_profile_pic": "https://media.licdn.com/dms/image/v2/C4D0BAQF8H-SLmMDZlA/company-logo_100_100/company-logo_100_100/0/1646683330132/hubspot_logo?e=2147483647&v=beta",
  "num_connections": null,
  "video_duration": null,
  "external_link_data": null,
  "video_thumbnail": null,
  "document_cover_image": null,
  "document_page_count": null,
  "user_profile_pic": "https://media.licdn.com/dms/image/v2/C4D0BAQF8H-SLmMDZlA/company-logo_100_100/company-logo_100_100/0/1646683330132/hubspot_logo?e=2147483647&v=beta",
  "user_name": "HubSpot",
  "original_post_text": "Fantasy football is actually just pipeline management",
  "timestamp": "2026-09-16T03:18:23.686Z",
  "input": {
    "url": "https://www.linkedin.com/feed/update/urn:li:activity:7503504518433878017"
  },
  "discovery_input": {
    "url": "https://www.linkedin.com/company/hubspot"
  }
}
```

**Error record** — the one shape a failed input takes:
```json
{
  "timestamp": "2026-09-16T03:21:49.135Z",
  "input": {"url": "https://www.linkedin.com/company/zq-no-such-company-x7k2p"},
  "error": "4XX page - dead page.",
  "error_code": "dead_page"
}
```

### Fields

Types as seen across the ten captured records, in the order the API sends
them:

| Field | Type | Description |
|-------|------|-------------|
| `url` | string | Post permalink |
| `id` | string | Activity id, nineteen digits; the record's identity |
| `user_id` | string | Company slug, the last path segment of the company URL |
| `use_url` | string | Company page URL; half the records carried a `?trk=public_post_feed-actor-image` suffix |
| `title` | string | Page title: headline, author and comment count |
| `headline` | string | First line of the post (eight of ten) |
| `post_text` | string | Plain text, newlines kept |
| `date_posted` | string | ISO 8601, milliseconds, `Z` |
| `hashtags` | array of string or null | With the `#` |
| `embedded_links` | array of string or null | Links in the text, hashtag feeds included |
| `images` | array of string or null | `media.licdn.com` URLs |
| `videos` | array of string or null | `dms.licdn.com` playlist URLs |
| `num_likes` | integer | Reactions |
| `num_comments` | integer | Comments |
| `more_articles_by_user` | null | Null in every record |
| `more_relevant_posts` | array of object or null | Other people's posts LinkedIn shows alongside (one of ten) |
| `top_visible_comments` | array of object | One to ten comments: `use_url`, `user_id`, `user_name`, `comment_date`, `comment`, `tagged_users`, `num_reactions`, `user_title`, `comment_images`, `comment_id`, `comment_url` |
| `user_followers` | integer | The company's follower count at scrape time |
| `user_posts` | integer | `0` in every record |
| `user_articles` | integer | `0` in every record |
| `post_type` | string | `post` |
| `account_type` | string | `Organization` |
| `post_text_html` | string | `post_text` with `<br/>` for newlines |
| `repost` | object | Four keys, all null when the post is original: `repost_hangtags`, `repost_attachments`, `tagged_users`, `tagged_companies` |
| `tagged_companies` | array | `[]` in every record |
| `tagged_people` | array | `[]` in every record |
| `user_title` | null | Null in every record |
| `author_profile_pic` | string | Company logo URL |
| `num_connections` | null | Null in every record |
| `video_duration` | integer or null | Seconds, when `videos` is set |
| `external_link_data` | null | Null in every record |
| `video_thumbnail` | string or null | When `videos` is set |
| `document_cover_image` | null | Null in every record |
| `document_page_count` | null | Null in every record |
| `user_profile_pic` | string | Same URL as `author_profile_pic` |
| `user_name` | string | Company display name |
| `original_post_text` | string | Differs from `post_text` in six of ten, by whitespace and trailing links |
| `timestamp` | string | Scrape time, ISO 8601 |
| `input` | object | `{"url": "https://www.linkedin.com/feed/update/urn:li:activity:<id>"}` |
| `discovery_input` | object | `{"url": …}`, the company URL as sent |

The ten posts of one company spanned 29 days.

## Error Responses

| HTTP Status | Body | Meaning |
|-------------|------|---------|
| 202 | JSON `{"status": "running", "message": …}` | Snapshot not ready |
| 400 | text or JSON | Bad `discover_by`, `type`, or body |
| 401 | text | Missing, empty or unrecognised token |
| 404 | text | Unknown dataset or snapshot |

## Notes

- Only delivered records are charged, so an unknown company slug costs
  nothing: the trigger accepts it, the ready body counts it under `errors`
  and `error_codes.dead_page`, and the snapshot carries one error record
- `POST /datasets/v3/snapshot/{id}/cancel` stops a running collection; the
  progress body then reads `canceled` with `error_codes.aborted_page`
- `limit_per_input` caps posts per company, most recent first

## The stand-in

- Any non-empty bearer passes. A missing header answers `Credentials are
  missing`; anything else that is not a bearer answers `Auth method is not
  supported`, so `Basic` does not get its own message
- The trigger validates `dataset_id`, `discover_by` and the body; `type`,
  `format`, `include_errors` and `limit_per_input` are accepted unread. A
  lone object is taken as one input, as the real API does; the `{"input":
  [...]}` wrapper is not. The item error lists only the missing `url`, and an
  empty body shares the non-JSON message
- `snapshot_id` is the URL-safe base64 of the comma-joined company slugs
  (`aHVic3BvdCx6b2hvLGZyZXNod29ya3MtaW5j` for hubspot, zoho, freshworks-inc),
  so progress and snapshot need no store beyond one set of ids already asked
- Progress answers `running` the first time an id is asked and `ready` from
  then on (a module-level set, forgotten when the mock restarts).
  `running_time` and the durations are constants. `starting`, `failed` and
  `canceled` never happen, and the cancel route is not mounted
- Downloading before the first progress ask answers the real 202 body
- Records are `world.spy_posts(slug)` completed to the forty real keys, in
  the real order. The world sets `repost` to null where the API sends the
  four-key object, and `embedded_links` and `images` to `[]` where the API
  sends null; `top_visible_comments` is always `[]`, `more_relevant_posts`
  null, `title` and `user_name` are both the company name, `timestamp` is the
  anchor day at noon, and `use_url` never carries the `?trk=` suffix
- An unknown slug yields the `dead_page` error record and `error_codes` on
  the ready body

## Reference

- [LinkedIn posts — discover by company URL](https://docs.brightdata.com/api-reference/scrapers/social-media-apis/linkedin-posts-discover-by-company-url)
- [Monitor progress](https://docs.brightdata.com/api-reference/web-scraper-api/management-apis/monitor-progress)
- [Web Scraper API pricing](https://brightdata.com/pricing/web-scraper)
