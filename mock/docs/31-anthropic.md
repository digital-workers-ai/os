# Anthropic Messages API (Claude with web search)

## Overview

Claude answers one tracked query per request with the `web_search` server tool
switched on. The API runs the search on Anthropic's side and returns, in one
message, the search it made, the pages it read and an answer whose claims cite
those pages. This is the only Anthropic surface the estate reads.

Captured on 2026-09-15 with `claude-haiku-4-5` and the tool
`web_search_20250305`: two queries, plus the three error bodies below. The
model id is an alias; the response names the snapshot it resolved to,
`claude-haiku-4-5-20251001`. One of the two queries ("crm with ai assistant")
came back without any search at all, see [Answers without a
search](#answers-without-a-search).

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

Without the key, 401. The key check runs first: a request with neither header
gets this body.

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

With a key the API does not recognise, 401, and `request_id` is null:

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

With a valid key and no `anthropic-version`, 400:

```json
{
  "type": "error",
  "error": {
    "type": "invalid_request_error",
    "message": "anthropic-version: header is required"
  },
  "request_id": "req_011Cf6QoXLEGEje5dUH2hNPY"
}
```

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

**Example Response** (real, trimmed: two of six search results, eight of
twenty-two content blocks, encrypted fields cut short):
```json
{
  "model": "claude-haiku-4-5-20251001",
  "id": "msg_011Cf6Qnc6D6oXqDtPLcxLcm",
  "type": "message",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "I'll search for current information about the best CRM options for small businesses."
    },
    {
      "type": "server_tool_use",
      "id": "srvtoolu_01Js6anQWAzUPu3zpJ4M1oJn",
      "name": "web_search",
      "input": {
        "query": "best CRM for small business 2026"
      }
    },
    {
      "type": "web_search_tool_result",
      "tool_use_id": "srvtoolu_01Js6anQWAzUPu3zpJ4M1oJn",
      "content": [
        {
          "type": "web_search_result",
          "title": "Best Small Business CRM in 2026 | Salesforce",
          "url": "https://www.salesforce.com/crm/crm-for-small-business/best-crm/",
          "encrypted_content": "EsQICioIExgCIiQ2NzI0ZDFj…",
          "page_age": "3 weeks ago"
        },
        {
          "type": "web_search_result",
          "title": "Best CRM for Small Business in 2026 | Slack",
          "url": "https://slack.com/blog/crm/best-crm-for-small-business",
          "encrypted_content": "EuAQCioIExgCIiQ2NzI0ZDFj…",
          "page_age": null
        }
      ],
      "caller": {
        "type": "direct"
      }
    },
    {
      "type": "text",
      "text": "Based on recent information, here are some of the best CRM options for small businesses:\n\n## Top Recommendations\n\n**Salesforce Starter**\n"
    },
    {
      "citations": [
        {
          "type": "web_search_result_location",
          "cited_text": "Best for most small businesses, in most cases: Salesforce\n\nSalesforce is the go-to CRM for many small businesses and for good reason. The platform can...",
          "url": "https://www.techradar.com/uk/news/software/-devices-based-around-software-we-can-t-control-it-s-terrifying-1206500",
          "title": "Best small business CRM of 2026",
          "encrypted_index": "EpMBCioIExgCIiQ2NzI0ZDFj…"
        }
      ],
      "type": "text",
      "text": "Salesforce is the go-to CRM for many small businesses, with a strong combination of ease-of-use, pricing, and extensive range of tools and features."
    },
    {
      "type": "text",
      "text": " "
    },
    {
      "citations": [
        {
          "type": "web_search_result_location",
          "cited_text": "Salesforce Starter Suite provides smaller teams with a powerful platform, simplified into a ready-to-use solution that takes minutes to set up. ",
          "url": "https://www.salesforce.com/crm/crm-for-small-business/best-crm/",
          "title": "Best Small Business CRM in 2026 | Salesforce",
          "encrypted_index": "Eo8BCioIExgCIiQ2NzI0ZDFj…"
        }
      ],
      "type": "text",
      "text": "It provides smaller teams with a powerful platform that takes minutes to set up."
    },
    {
      "type": "text",
      "text": " Consider your budget, team size, and which tools you're already using when making your decision."
    }
  ],
  "container": null,
  "stop_reason": "end_turn",
  "stop_sequence": null,
  "stop_details": null,
  "usage": {
    "input_tokens": 8875,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0,
    "cache_creation": {
      "ephemeral_5m_input_tokens": 0,
      "ephemeral_1h_input_tokens": 0
    },
    "output_tokens": 586,
    "service_tier": "standard",
    "inference_geo": "not_available",
    "server_tool_use": {
      "web_search_requests": 1,
      "web_fetch_requests": 0
    }
  }
}
```

### Fields

**Message**, keys in the order the API writes them:

| Field | Type | Description |
|-------|------|-------------|
| `model` | string | The snapshot that answered, `claude-haiku-4-5-20251001` for the alias |
| `id` | string | `msg_` followed by 26 characters |
| `type` | string | Always `message` |
| `role` | string | Always `assistant` |
| `content` | array | Content blocks, in the order they were produced |
| `container` | null | Only set when code execution ran |
| `stop_reason` | string | `end_turn` when the answer is complete; `max_tokens`, `pause_turn`, `tool_use`, `refusal` otherwise |
| `stop_sequence` | null | Set only when a custom stop sequence fired |
| `stop_details` | null | Set only on `refusal` |
| `usage` | object | Token and search counts |

**Content blocks**, in the order the API produces them:

| Block `type` | Keys | Description |
|--------------|------|-------------|
| `text` (leading) | `type`, `text` | Claude announcing the search, in its own words |
| `server_tool_use` | `type`, `id`, `name`, `input` | One per search. `id` is `srvtoolu_` + 26 characters, `name` is `web_search`, `input.query` is the search Claude wrote (it added the year), not the user's text |
| `web_search_tool_result` | `type`, `tool_use_id`, `content`, `caller` | One per search; `tool_use_id` points at its `server_tool_use`; `caller` is `{"type": "direct"}`. `content` is a list of `web_search_result` (six for one search here), or a single error object |
| `text` (cited) | `citations`, `type`, `text` | One block per cited claim, a sentence or part of one, with one citation |
| `text` (uncited) | `type`, `text` | Everything between cited claims: the intro, a lone `" "`, markdown headings such as `"\n\n**Zoho CRM**\n"`, the closing sentence |

**`web_search_result`** — one per page read:

| Key | Type | Description |
|-----|------|-------------|
| `type` | string | `web_search_result` |
| `title` | string | Page title |
| `url` | string | Page URL |
| `encrypted_content` | string | Opaque blob, 1,300 to 2,900 characters, to pass back on later turns |
| `page_age` | string or null | `3 weeks ago`, `June 19, 2026`, or null |

**`web_search_result_location`** — the citation on a cited block:

| Key | Type | Description |
|-----|------|-------------|
| `type` | string | `web_search_result_location` |
| `cited_text` | string | A quote of the source page, not of the answer: up to 150 characters, then `...` when cut |
| `url` | string | Cited page URL, always one of the `web_search_result` urls |
| `title` | string | Cited page title |
| `encrypted_index` | string | Opaque reference, about 200 characters, to pass back on later turns |

**`usage`**, keys in order:

| Key | Type | Description |
|-----|------|-------------|
| `input_tokens` | int | Includes the search results Claude read |
| `cache_creation_input_tokens` | int | |
| `cache_read_input_tokens` | int | |
| `cache_creation` | object | `ephemeral_5m_input_tokens`, `ephemeral_1h_input_tokens` |
| `output_tokens` | int | |
| `service_tier` | string | `standard` |
| `inference_geo` | string | `not_available` |
| `server_tool_use` | object | `web_search_requests`, `web_fetch_requests`; absent when nothing was searched |

### Answers without a search

Claude decides whether to search. For "crm with ai assistant" it did not, and
asked what the user meant instead. The message then has one `text` block with
no `citations`, no `server_tool_use` or `web_search_tool_result`, and no
`server_tool_use` in `usage`:

```json
{
  "model": "claude-haiku-4-5-20251001",
  "id": "msg_011Cf6QoBVsfpFUEdUjiDvLC",
  "type": "message",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "I'd be happy to help you with information about CRM with AI assistants! To give you the most relevant and current information, could you clarify what you're looking for?\n\nAre you interested in:\n\n1. **Overview of CRM systems with AI capabilities** - How AI is being integrated into customer relationship management platforms?\n\n…"
    }
  ],
  "container": null,
  "stop_reason": "end_turn",
  "stop_sequence": null,
  "stop_details": null,
  "usage": {
    "input_tokens": 2218,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0,
    "cache_creation": {
      "ephemeral_5m_input_tokens": 0,
      "ephemeral_1h_input_tokens": 0
    },
    "output_tokens": 176,
    "service_tier": "standard",
    "inference_geo": "not_available"
  }
}
```

A pull that concatenates `text` blocks and collects citation urls gets a plain
answer with zero sources from such a message; that is a real outcome, not a
failure.

### Search errors

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
| 404 | `not_found_error` | Unknown route, or a model the organization cannot use |
| 413 | `request_too_large` | Body over 32 MB |
| 429 | `rate_limit_error` | Rate limit or spend cap; `retry-after` header |
| 500 | `api_error` | Anthropic-side failure |
| 529 | `overloaded_error` | Temporary overload |

A model the API does not serve, 404 (captured):

```json
{
  "type": "error",
  "error": {
    "type": "not_found_error",
    "message": "model: claude-haiku-9-9"
  },
  "request_id": "req_011Cf6QoNKW4BTkQS6aE7oXR"
}
```

A model the organization cannot use answers the same way, so the message never
reveals whether the id exists.

## Pricing

Web search costs **$10 per 1,000 searches** on top of tokens. Each search
counts once whatever it returns, a failed search is not billed, and the results
Claude reads count as input tokens on this turn and on every later turn that
carries them. Claude Haiku 4.5 is $1 per million input tokens and $5 per
million output tokens; the searched answer above cost about 2.2 cents and the
unsearched one about 0.3 cents. Citation fields (`cited_text`, `title`, `url`)
are not billed.

## Notes

- `web_search_20250305` is the tool version for Claude Haiku 4.5. The newer
  `web_search_20260209` and `web_search_20260318` add dynamic filtering and
  need Claude 4.6 or later; on those versions the tool defaults to being
  called from code execution, and a model without programmatic tool calling
  needs `allowed_callers: ["direct"]` or the request answers 400
- `max_uses` is a ceiling, not a count: this capture searched once for a
  ceiling of three, and Claude may also not search at all
- A hook that concatenates every `text` block also gets the leading
  announcement and the markdown headings between cited claims
- A cited claim can be part of a sentence, with the rest of the sentence in the
  next uncited block, so cited blocks do not split the answer at sentence
  boundaries
- `encrypted_content` and `encrypted_index` only matter when the message is
  sent back for another turn; a single-turn pull can ignore them

## What the stand-in leaves out

- Exactly one search per request with three results; the real API may search
  up to `max_uses` times, return six or more results, or not search at all
- The leading text block is one fixed sentence that never names the query or a
  company; the real one paraphrases the query. `input.query` is the user's
  text with the year appended, a stand-in for Claude's rewrite
- Answer blocks cut at whole sentences: a sentence naming a cited company is
  one cited block carrying one citation per such company, and everything
  between two cited sentences is one uncited block. The real API cites
  claims, not sentences, one citation per block
- `cited_text` is the page title, a blank line and the sentence, cut at 150
  characters with `...`; the real one quotes the page. The world has no page
  text to quote
- `encrypted_content` and `encrypted_index` are deterministic hashes (1,368
  and 216 characters); only the real API can decrypt real ones, so a stand-in
  message cannot be replayed to `api.anthropic.com`
- `page_age` is always `Month D, YYYY`; the real one is also `3 weeks ago` or
  null
- Two model ids are accepted, `claude-haiku-4-5` and
  `claude-haiku-4-5-20251001`, both answering as the snapshot
- No streaming, no `system`, `tool_choice`, `allowed_domains`,
  `blocked_domains` or `user_location`, no rate limiting, no search-level
  error objects
- `request_id` in error bodies is deterministic; the real ids are unique per
  request, and null on an invalid key

## Reference

- [Web search tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)
- [Server tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/server-tools)
- [Tool reference](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-reference)
- [Messages API](https://platform.claude.com/docs/en/api/messages)
- [Errors](https://platform.claude.com/docs/en/api/errors)
- [Versions](https://platform.claude.com/docs/en/api/versioning)
- [Pricing](https://platform.claude.com/docs/en/pricing)
