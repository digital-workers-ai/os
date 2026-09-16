# Anthropic Messages API (Claude with web search)

## Overview

Claude answers one tracked query per request with the `web_search` server tool
switched on. The API runs the search on Anthropic's side and returns, in one
message, the search it made, the pages it read and an answer whose sentences
cite those pages. This is the only Anthropic surface the estate reads.

Where this contract comes from: the key in `app/.env` was rejected by the API
on 2026-09-15 (`authentication_error`, "API key is invalid."; the stored value
is 39 characters, a real key is about 108), so there is no live capture yet.
The request below is the one the plan specifies and the docs show. The
response shape is the documented example from the web search tool page,
cross-checked against the field lists of the `anthropic` Python SDK 1.5.0
(`Message`, `Usage`, `ServerToolUseBlock`, `WebSearchToolResultBlock`,
`WebSearchResultBlock`, `TextBlock`, `CitationsWebSearchResultLocation`). The
two authentication bodies were captured live; they need no valid key. A
capture with a working key should replace the example response here.

## Base URL

```
https://api.anthropic.com
```

The stand-in mounts the same paths under `/anthropic`.

## Authentication

An API key in `x-api-key` and an API version in `anthropic-version` on every
request.

```
x-api-key: <key>
anthropic-version: 2023-06-01
content-type: application/json
```

Without the key, 401 (captured):

```json
{
  "type": "error",
  "error": {
    "type": "authentication_error",
    "message": "x-api-key header is required"
  },
  "request_id": "req_011Cf6PsveC3pBH3n4HPVUse"
}
```

With a key the API does not recognise, 401 (captured), and `request_id` is
null:

```json
{
  "type": "error",
  "error": {
    "type": "authentication_error",
    "message": "API key is invalid."
  },
  "request_id": null
}
```

The key check runs first: a request with neither header gets the `x-api-key`
body (captured), so the missing-`anthropic-version` body could not be captured
without a valid key. The versioning page says the header is required. The
stand-in answers 400 with the same envelope and the message
`anthropic-version header is required`; that message follows the phrasing of
the captured key body and is unverified.

The stand-in accepts any non-empty key.

## Rate Limits

Per organization, by usage tier, on requests and tokens per minute. HTTP 429
`rate_limit_error` with a `retry-after` header when exceeded. Web search has
its own per-organization search rate limit, shown on the Console's rate-limits
page.

---

## Endpoints

### POST /v1/messages

One turn of a conversation. With the web search tool in `tools`, the API runs
a server-side loop (search, read, answer) inside the one request.

**Body:**
| Field | Type | Description |
|-------|------|-------------|
| `model` | string | `claude-haiku-4-5`. An id the API does not serve answers 404 |
| `max_tokens` | int | Output cap; `1024` |
| `messages` | array | `[{"role": "user", "content": "<query>"}]` |
| `tools` | array | `[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]` |

**Example Request:**
```bash
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-haiku-4-5",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "best crm for small business"}],
    "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]
  }'
```

**Example Response** (the documented example, trimmed; `type`, `model` and
`stop_sequence` are always present and the docs leave them out):
```json
{
  "id": "msg_a930390d3a",
  "type": "message",
  "role": "assistant",
  "model": "claude-haiku-4-5",
  "content": [
    {
      "type": "text",
      "text": "I'll search for when Claude Shannon was born."
    },
    {
      "type": "server_tool_use",
      "id": "srvtoolu_01WYG3ziw53XMcoyKL4XcZmE",
      "name": "web_search",
      "input": {
        "query": "claude shannon birth date"
      }
    },
    {
      "type": "web_search_tool_result",
      "tool_use_id": "srvtoolu_01WYG3ziw53XMcoyKL4XcZmE",
      "content": [
        {
          "type": "web_search_result",
          "url": "https://en.wikipedia.org/wiki/Claude_Shannon",
          "title": "Claude Shannon - Wikipedia",
          "encrypted_content": "EqgfCioIARgBIiQ3YTAwMjY1Mi1mZjM5LTQ1NGUtODgxNC1kNjNjNTk1ZWI3Y...",
          "page_age": "April 30, 2025"
        }
      ]
    },
    {
      "type": "text",
      "text": "Based on the search results, "
    },
    {
      "type": "text",
      "text": "Claude Shannon was born on April 30, 1916, in Petoskey, Michigan",
      "citations": [
        {
          "type": "web_search_result_location",
          "url": "https://en.wikipedia.org/wiki/Claude_Shannon",
          "title": "Claude Shannon - Wikipedia",
          "encrypted_index": "Eo8BCioIAhgBIiQyYjQ0OWJmZi1lNm..",
          "cited_text": "Claude Elwood Shannon (April 30, 1916 – February 24, 2001) was an American mathematician, electrical engineer, computer scientist, cryptographer and i..."
        }
      ]
    }
  ],
  "stop_reason": "end_turn",
  "stop_sequence": null,
  "usage": {
    "input_tokens": 6039,
    "output_tokens": 931,
    "server_tool_use": {
      "web_search_requests": 1
    }
  }
}
```

### Fields

**Message:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | `msg_` followed by 26 characters |
| `type` | string | Always `message` |
| `role` | string | Always `assistant` |
| `model` | string | The model that answered |
| `content` | array | Content blocks, in the order they were produced |
| `stop_reason` | string | `end_turn` when the answer is complete; `max_tokens`, `pause_turn`, `tool_use`, `refusal` otherwise |
| `stop_sequence` | string or null | Null unless a custom stop sequence fired |
| `usage` | object | Token and search counts |

**Content blocks**, in the order the API produces them:

| Block `type` | Keys | Description |
|--------------|------|-------------|
| `text` (leading) | `type`, `text` | Optional. Claude announcing the search; no `citations` key |
| `server_tool_use` | `type`, `id`, `name`, `input` | One per search. `id` is `srvtoolu_` + 26 characters, `name` is `web_search`, `input.query` is the search Claude wrote, not the user's text verbatim |
| `web_search_tool_result` | `type`, `tool_use_id`, `content` | One per search; `tool_use_id` points at its `server_tool_use`. `content` is a list of `web_search_result`, or a single error object |
| `text` (answer) | `type`, `text`, `citations` | One block per cited span, `citations` a list of `web_search_result_location`. Uncited spans come as `text` blocks with no `citations` key |

**`web_search_result`** — one per page read:

| Key | Type | Description |
|-----|------|-------------|
| `type` | string | `web_search_result` |
| `url` | string | Page URL |
| `title` | string | Page title |
| `encrypted_content` | string | Opaque blob to pass back on later turns |
| `page_age` | string or null | When the page was last updated, e.g. `April 30, 2025` |

**`web_search_result_location`** — one per source a span rests on:

| Key | Type | Description |
|-----|------|-------------|
| `type` | string | `web_search_result_location` |
| `url` | string | Cited page URL |
| `title` | string or null | Cited page title |
| `encrypted_index` | string | Opaque reference to pass back on later turns |
| `cited_text` | string | Up to 150 characters of the cited page, not of the answer |

**`usage`:**

| Key | Type | Description |
|-----|------|-------------|
| `input_tokens` | int | Includes the search results Claude read |
| `output_tokens` | int | |
| `cache_creation_input_tokens` | int | |
| `cache_read_input_tokens` | int | |
| `cache_creation` | object | `ephemeral_5m_input_tokens`, `ephemeral_1h_input_tokens` |
| `service_tier` | string | `standard`, `priority` or `batch` |
| `server_tool_use` | object | `web_search_requests`, `web_fetch_requests` |

A search that fails does not raise: the message is still 200 and the
`web_search_tool_result.content` is one object instead of a list:

```json
{
  "type": "web_search_tool_result",
  "tool_use_id": "srvtoolu_a93jad",
  "content": {
    "type": "web_search_tool_result_error",
    "error_code": "max_uses_exceeded"
  }
}
```

Error codes: `too_many_requests`, `invalid_tool_input`, `max_uses_exceeded`,
`query_too_long`, `request_too_large`, `unavailable`. A search that succeeds
with no hits returns an empty `content` list.

## Error Responses

Every error is JSON with the same envelope: `type: "error"`, an `error` object
with `type` and `message`, and a `request_id`.

| HTTP Status | `error.type` | Meaning |
|-------------|--------------|---------|
| 400 | `invalid_request_error` | Bad body or header, web search disabled for the organization, both domain lists at once |
| 401 | `authentication_error` | Missing, malformed or revoked key |
| 403 | `permission_error` | Key not allowed to use the resource |
| 404 | `not_found_error` | Unknown route, or a model the organization cannot use: message `model: <id>` |
| 413 | `request_too_large` | Body over 32 MB |
| 429 | `rate_limit_error` | Rate limit or spend cap; `retry-after` header |
| 500 | `api_error` | Anthropic-side failure |
| 529 | `overloaded_error` | Temporary overload |

A model the API does not serve and a model the organization cannot use return
the same 404, so the message never reveals whether the id exists.

## Pricing

Web search costs **$10 per 1,000 searches** on top of tokens. Each search
counts once whatever it returns, a failed search is not billed, and the results
Claude reads count as input tokens on this turn and on every later turn that
carries them. Claude Haiku 4.5 is $1 per million input tokens and $5 per
million output tokens. Citation fields (`cited_text`, `title`, `url`) are not
billed.

## Notes

- `web_search_20250305` is the tool version for Claude Haiku 4.5. The newer
  `web_search_20260209` and `web_search_20260318` add dynamic filtering and
  need Claude 4.6 or later; on those versions the tool defaults to being
  called from code execution, and a model without programmatic tool calling
  needs `allowed_callers: ["direct"]` or the request answers 400
- `max_uses` is a ceiling, not a count: Claude may search fewer times, and a
  comparative query can produce several `server_tool_use` and
  `web_search_tool_result` pairs before the answer
- A hook that concatenates every `text` block also picks up the leading
  "I'll search for..." block when Claude emits one
- `encrypted_content` and `encrypted_index` only matter when the message is
  sent back for another turn; a single-turn pull can ignore them
- `model` in the response may be the dated snapshot the alias resolves to; not
  verified without a working key

## What the stand-in leaves out

- Exactly one search per request, and `input.query` is the user's text
  verbatim; the real API rewrites the query and may search up to `max_uses`
  times
- No leading uncited "I'll search" text block
- The answer comes as exactly two `text` blocks, each carrying one citation per
  sentence that names a cited company; the real API cuts a new block at every
  cited span. `cited_text` is the answer sentence (at most 150 characters)
  because the world has no page text to quote; the real API quotes the page
- `encrypted_content` and `encrypted_index` are deterministic hashes (344 and
  44 characters); real ones are far longer and only the real API can decrypt
  them, so a stand-in message cannot be replayed to `api.anthropic.com`
- `container` and `stop_details` on the message, `inference_geo` and
  `output_tokens_details` in `usage`, all null or absent on a plain request,
  are not sent
- Eight model ids are accepted (`claude-haiku-4-5`,
  `claude-haiku-4-5-20251001`, `claude-sonnet-4-6`, `claude-sonnet-5`,
  `claude-opus-4-6`, `claude-opus-4-7`, `claude-opus-4-8`, `claude-opus-5`);
  the response echoes the requested id
- No streaming, no `system`, `tool_choice`, `allowed_domains`,
  `blocked_domains` or `user_location`, no rate limiting, no search-level
  error objects
- `request_id` in error bodies is deterministic

## Reference

- [Web search tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)
- [Server tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/server-tools)
- [Tool reference](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-reference)
- [Messages API](https://platform.claude.com/docs/en/api/messages)
- [Errors](https://platform.claude.com/docs/en/api/errors)
- [Versions](https://platform.claude.com/docs/en/api/versioning)
- [Pricing](https://platform.claude.com/docs/en/pricing)
