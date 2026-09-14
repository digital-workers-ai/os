# X API v2 (Organic Posts)

## Overview

The X API v2 serves the posts of one account through its user timeline. This
is the only X surface the estate reads: the authenticated account's own posts,
with the public engagement counters each one carries.

The Ads API is a different product on a different host and is **not** part of
this contract — see [What is not here](#what-is-not-here).

## Base URL

```
https://api.x.com
```

The stand-in mounts the same paths under `/twitter`.

## Authentication

OAuth 2.0 App-Only: a bearer token issued to the app, sent on every request.

```
Authorization: Bearer <token>
```

Returns 401 with no token:

```json
{
  "title": "Unauthorized",
  "type": "about:blank",
  "status": 401,
  "detail": "Unauthorized"
}
```

App-only tokens carry no user context. Endpoints that resolve "the current
user" refuse them:

```bash
curl -H "Authorization: Bearer <token>" "https://api.x.com/2/users/me"
```

```json
{
  "title": "Unsupported Authentication",
  "detail": "Authenticating with OAuth 2.0 Application-Only is forbidden for this endpoint.  Supported authentication types are [OAuth 1.0a User Context, OAuth 2.0 User Context].",
  "type": "https://api.twitter.com/2/problems/unsupported-authentication",
  "status": 403
}
```

So the account whose timeline is being read has to be named by its numeric id,
which the app-only token cannot discover for itself.

## Rate Limits

Per app and per endpoint, in fifteen-minute windows, with headers on every
response:

```
x-rate-limit-limit: 900
x-rate-limit-remaining: 899
x-rate-limit-reset: 1720500000
```

HTTP 429 when exceeded; `x-rate-limit-reset` is the epoch second the window
rolls over. Accounts on the pay-per-use plan are also billed per request, so a
pull asks for the largest page it can rather than many small ones.

---

## Endpoints

### GET /2/users/{id}/tweets

The posts of one user, newest first.

**Path Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `id` | string | Numeric user id. `me` is **not** accepted here |

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `max_results` | int | 10 | Page size (5-100) |
| `start_time` | string | — | RFC 3339 timestamp, inclusive |
| `end_time` | string | — | RFC 3339 timestamp, exclusive |
| `pagination_token` | string | — | `meta.next_token` from the previous page |
| `tweet.fields` | string | — | Comma-separated extra fields |

**Example Request:**
```bash
curl -H "Authorization: Bearer <token>" \
  "https://api.x.com/2/users/4030300010/tweets?max_results=100&tweet.fields=created_at,public_metrics"
```

**Example Response:**
```json
{
  "data": [
    {
      "created_at": "2026-09-04T15:00:00.000Z",
      "edit_history_tweet_ids": ["1990300010000000001"],
      "id": "1990300010000000001",
      "public_metrics": {
        "bookmark_count": 11,
        "impression_count": 4200,
        "like_count": 120,
        "quote_count": 3,
        "reply_count": 7,
        "retweet_count": 18
      },
      "text": "We just shipped a faster sync. Details in the thread."
    }
  ],
  "meta": {
    "newest_id": "1990300010000000001",
    "oldest_id": "1990300010000000001",
    "result_count": 1,
    "next_token": "7140dibdnow9c7btwoxjsaanojcvvdl31jpynu8ohfn74"
  }
}
```

### Fields

Three fields come back whether or not they are asked for:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Post id, a numeric string |
| `text` | string | Post body |
| `edit_history_tweet_ids` | array of string | Every version of this post, oldest first |

`tweet.fields` adds the rest. The two this estate asks for:

| Field | Type | Description |
|-------|------|-------------|
| `created_at` | string | RFC 3339, milliseconds, `Z` |
| `public_metrics` | object | Engagement counters |

A field that is not asked for is not in the response — there is no partial
object and no null placeholder.

**`public_metrics`** — six integers, all always present:

| Key | Description |
|-----|-------------|
| `impression_count` | Times the post was seen |
| `like_count` | Likes |
| `retweet_count` | Reposts |
| `reply_count` | Replies |
| `quote_count` | Quote posts |
| `bookmark_count` | Bookmarks |

Counters can legitimately be `0`: reposts of somebody else's post report a
`retweet_count` inherited from the original and zero for everything else.

There is no geography, language or author field on a post unless it is asked
for, and no `country_code` at any tier.

## Pagination

Token-based, in `meta`:

```json
{
  "meta": {
    "result_count": 100,
    "newest_id": "1990300010000000100",
    "oldest_id": "1990300010000000001",
    "next_token": "7140dibdnow9c7btwoxjsaanojcvvdl31jpynu8ohfn74"
  }
}
```

- Pass `pagination_token` with the `next_token` value for the next page
- No `next_token` means the last page
- An empty page omits `data` entirely rather than sending `[]`
- `meta.result_count` is the size of this page, not of the whole timeline

## Error Responses

| HTTP Status | Title | Meaning |
|-------------|-------|---------|
| 400 | Invalid Request | Bad parameter value, including a non-numeric `id` |
| 401 | Unauthorized | Missing, malformed or revoked token |
| 403 | Unsupported Authentication | Endpoint needs user context, not app-only |
| 404 | Not Found | No such route |
| 429 | Too Many Requests | Rate limit or spend cap reached |

A bad user id names itself:

```json
{
  "title": "Invalid Request",
  "detail": "One or more parameters to your request was invalid.",
  "type": "https://api.x.com/2/problems/invalid-request",
  "errors": [
    {
      "message": "The `id` query parameter value [me] is not valid",
      "parameters": { "id": ["me"] }
    }
  ]
}
```

## Notes

- The timeline holds the most recent 3,200 posts; `start_time` and `end_time`
  narrow that, they do not reach past it
- Reposts appear in the timeline as their own posts, with `RT @handle` text
- A numeric id that belongs to somebody else answers 200 with their posts, so
  the wrong id is silently the wrong account, never an error
- The stand-in accepts `me` as the id and answers with its own account's
  posts, which the real API does not do: it keeps an estate with no account
  configured from being an estate with no posts

## What is not here

`GET /12/accounts` and the rest of the campaign, line item and stats surface
belong to the **X Ads API**, which is a separate product:

- It lives on `https://ads-api.x.com`, not `https://api.x.com` — the same path
  on this host answers 404
- It needs an Ads API authorization granted per developer account, and answers
  401 without one
- It authenticates with OAuth 1.0a signed requests, not an app-only bearer

Nothing in this estate reads it, and the stand-in does not answer for it.

## Reference

- [X API v2 Overview](https://docs.x.com/x-api/introduction)
- [User Posts Timeline](https://docs.x.com/x-api/posts/user-posts-timeline-by-user-id)
- [App-Only Authentication](https://docs.x.com/fundamentals/authentication/oauth-2-0/application-only)
- [Post Fields](https://docs.x.com/x-api/fundamentals/data-dictionary)
- [Pagination](https://docs.x.com/x-api/fundamentals/pagination)
- [Rate Limits](https://docs.x.com/x-api/fundamentals/rate-limits)
