# OpenRouter (ChatGPT, Perplexity, Gemini)

## Overview

OpenRouter fronts many model vendors behind one OpenAI-compatible endpoint
and one key. Spy asks it the tracked queries three times, once per model, and
reads the answer text plus the web citations each vendor attaches. The same
endpoint reads the text off a Google Ads creative preview when given an
`image_url` part.

Everything below was captured against the real API on 2026-09-15 with the
key in `app/.env`; requests and response shapes are copied from those
captures, content is not.

## Base URL

```
https://openrouter.ai
```

The stand-in mounts the same path under `/openrouter`.

## Authentication

A bearer token on every request:

```
Authorization: Bearer <key>
Content-Type: application/json
```

Returns 401 with no token:

```json
{
  "error": {
    "message": "No cookie auth credentials found",
    "code": 401
  }
}
```

The stand-in accepts any non-empty bearer and answers the same body without
one.

## Pricing

Per-token rates plus a per-search or per-request fee, as billed on the
captures (`usage.cost_details`):

| Model | Input | Output | Search |
|-------|-------|--------|--------|
| `openai/gpt-5.6-luna` | $0.20 /M | $1.20 /M | $10 per 1,000 web searches |
| `perplexity/sonar` | $1.00 /M | $1.00 /M | $5 per 1,000 requests |
| `google/gemini-3.5-flash-lite` | $0.30 /M | $2.50 /M | $14 per 1,000 grounded searches |

One query on GPT cost $0.026 (two searches, 21k prompt tokens of search
results), on Sonar $0.005, on Gemini $0.031 (two searches). One image read
on GPT cost $0.0008. The four content captures plus two error probes came to
$0.063.

---

## Endpoints

### POST /api/v1/chat/completions

One answer to one conversation. Spy sends a single user message per request.

**Body:**
| Field | Type | Description |
|-------|------|-------------|
| `model` | string | One of the three ids below |
| `messages` | array | `[{"role": "user", "content": <string or parts>}]` |
| `plugins` | array | `[{"id": "web", "engine": "native", "max_results": 5}]` for GPT and Gemini; absent for Sonar |

**The working request per model** (the connectors follow these exactly):

```bash
curl https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer <key>" -H "Content-Type: application/json" \
  -d '{"model": "openai/gpt-5.6-luna",
       "messages": [{"role": "user", "content": "best crm for small business"}],
       "plugins": [{"id": "web", "engine": "native", "max_results": 5}]}'
```

```bash
curl https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer <key>" -H "Content-Type: application/json" \
  -d '{"model": "perplexity/sonar",
       "messages": [{"role": "user", "content": "best crm for small business"}]}'
```

```bash
curl https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer <key>" -H "Content-Type: application/json" \
  -d '{"model": "google/gemini-3.5-flash-lite",
       "messages": [{"role": "user", "content": "best crm for small business"}],
       "plugins": [{"id": "web", "engine": "native", "max_results": 5}]}'
```

All three produced `annotations` on the first try; no `engine: "exa"` or
`:online` fallback was needed or captured.

**Example Response** (`openai/gpt-5.6-luna`, trimmed):
```json
{
  "id": "gen-1789528654-5WlfyzbKeCU25XiQWkP7",
  "object": "chat.completion",
  "created": 1789528654,
  "model": "openai/gpt-5.6-luna",
  "provider": "OpenAI",
  "system_fingerprint": null,
  "service_tier": "default",
  "choices": [
    {
      "index": 0,
      "logprobs": null,
      "finish_reason": "stop",
      "native_finish_reason": "completed",
      "message": {
        "role": "assistant",
        "content": "## Best CRM for most small businesses: **HubSpot CRM**\n\nHubSpot is usually the best starting point if you want something easy to adopt, with contact management, deal pipelines, email tracking, forms, and basic reporting. Its free CRM is available for up to two users, while paid Customer Platform plans currently start at $7 per seat/month under promotional pricing. ([hubspot.com](https://www.hubspot.com/pricing/suite?products=crm-suite-starter-bundle_1&utm_source=openai))\n\n### Best options by situation\n\n| CRM | Best for | ...",
        "refusal": null,
        "reasoning": "**Searching for CRM recommendations**\n\nI need to find some CRM recommendations, ...",
        "reasoning_details": [
          {"type": "reasoning.summary", "summary": "**Searching for CRM recommendations** ...", "format": "openai-responses-v1", "index": 0}
        ],
        "annotations": [
          {
            "type": "url_citation",
            "url_citation": {
              "url": "https://www.hubspot.com/pricing/suite?products=crm-suite-starter-bundle_1&utm_source=openai",
              "title": "Customer Platform Pricing | HubSpot",
              "start_index": 367,
              "end_index": 475
            }
          },
          {
            "type": "url_citation",
            "url_citation": {
              "url": "https://www.pipedrive.com/en/pricing?utm_source=openai",
              "title": "CRM Pricing Plans | Affordable CRM Software Costs | Pipedrive",
              "start_index": 1880,
              "end_index": 1953
            }
          }
        ]
      }
    }
  ],
  "usage": {
    "prompt_tokens": 21170,
    "completion_tokens": 957,
    "total_tokens": 22127,
    "cost": 0.02560135,
    "is_byok": false,
    "prompt_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 4379, "audio_tokens": 0, "video_tokens": 0},
    "cost_details": {"upstream_inference_cost": 0.02560135, "upstream_inference_prompt_cost": 0.00445295, "upstream_inference_completions_cost": 0.0011484},
    "completion_tokens_details": {"reasoning_tokens": 367, "image_tokens": 0, "audio_tokens": 0},
    "server_tool_use_details": {"web_search_requests": 2}
  }
}
```

**Example Response** (`perplexity/sonar`, trimmed):
```json
{
  "id": "gen-1789528670-69G3NWBcgFD1qVNA4n0h",
  "object": "chat.completion",
  "created": 1789528670,
  "model": "perplexity/sonar",
  "provider": "Perplexity",
  "system_fingerprint": null,
  "service_tier": null,
  "choices": [
    {
      "index": 0,
      "logprobs": null,
      "finish_reason": "stop",
      "native_finish_reason": "stop",
      "message": {
        "role": "assistant",
        "content": "The **best CRM for a small business** depends on your workflow, but the most common top pick is **HubSpot CRM** because it has a genuinely usable free plan and is widely recommended as the best overall starting point for small teams.[3][6][11]\n\nIf you want a quick shortlist, these are the strongest options by use case:\n- **HubSpot CRM** — best overall / best free starting point for most small businesses.[3][6][10][11]\n- **Pipedrive** — best for **sales-focused** teams that want a simple visual pipeline.[3][9][18]\n- **Zoho CRM** — ...",
        "refusal": null,
        "reasoning": null,
        "annotations": [
          {
            "type": "url_citation",
            "url_citation": {
              "url": "https://www.forbes.com/advisor/business/software/best-crm-small-business/",
              "title": "10 Best Small Business CRM Software Of 2026",
              "start_index": 0,
              "end_index": 0
            }
          },
          {
            "type": "url_citation",
            "url_citation": {
              "url": "https://innowise.com/blog/best-crm-for-small-business/",
              "title": "Reviews of the best CRMs for a small business in 2026",
              "start_index": 0,
              "end_index": 0
            }
          }
        ]
      }
    }
  ],
  "usage": {
    "prompt_tokens": 6,
    "completion_tokens": 422,
    "total_tokens": 428,
    "cost": 0.00543,
    "is_byok": false,
    "prompt_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0, "audio_tokens": 0, "video_tokens": 0},
    "cost_details": {"upstream_inference_cost": 0.00543, "upstream_inference_prompt_cost": 6e-06, "upstream_inference_completions_cost": 0.005424},
    "completion_tokens_details": {"reasoning_tokens": 0, "image_tokens": 0, "audio_tokens": 0}
  }
}
```

**Example Response** (`google/gemini-3.5-flash-lite`, trimmed):
```json
{
  "id": "gen-1789528676-4K1g4RGi9iHDiSZLi8kB",
  "object": "chat.completion",
  "created": 1789528676,
  "model": "google/gemini-3.5-flash-lite",
  "provider": "Google",
  "system_fingerprint": null,
  "service_tier": "default",
  "choices": [
    {
      "index": 0,
      "logprobs": null,
      "finish_reason": "stop",
      "native_finish_reason": "STOP",
      "message": {
        "role": "assistant",
        "content": "Choosing the \"best\" CRM for a small business depends heavily on your budget, your team's technical skill, and whether you primarily need to track sales pipelines, automate marketing, or manage client projects. \n\nThe top CRM options for small businesses are categorized below by what they do best:\n\n---\n\n### 1. HubSpot CRM — Best Overall & Best Free Tier\nIf you are just starting out or want a powerful system that won't immediately cost you a monthly subscription, HubSpot is widely considered the gold standard.\n...",
        "refusal": null,
        "reasoning": null,
        "reasoning_details": [
          {"type": "reasoning.text", "signature": "AY89a1/G2dvYND3nZupvcw8Y...", "format": "google-gemini-v1", "index": 0}
        ],
        "annotations": [
          {
            "type": "url_citation",
            "url_citation": {
              "url": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEUa41KyzVMaxiUV8zdA5HH5kJkPMe6DyW5zlBWzEjtRPJUUFNg5PGtc2zxmC-AtMkosj7WsLok1jrgXZzTpPl7Uj9Rnl3wcmtQrLwoxiVosxe8T2rfGB7lCrYKFthXTL2of4LYYdb1hCwaH5I_FaqR",
              "title": "innowise.com",
              "start_index": 0,
              "end_index": 208
            }
          },
          {
            "type": "url_citation",
            "url_citation": {
              "url": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH9Q0BYJwjhq...",
              "title": "ustechautomations.com",
              "start_index": 310,
              "end_index": 513
            }
          }
        ]
      }
    }
  ],
  "usage": {
    "prompt_tokens": 30,
    "completion_tokens": 1370,
    "total_tokens": 1400,
    "cost": 0.031434,
    "is_byok": false,
    "prompt_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0, "audio_tokens": 0, "video_tokens": 0},
    "cost_details": {"upstream_inference_cost": 0.031434, "upstream_inference_prompt_cost": 9e-06, "upstream_inference_completions_cost": 0.003425},
    "completion_tokens_details": {"reasoning_tokens": 0, "image_tokens": 0, "audio_tokens": 0},
    "server_tool_use_details": {"web_search_requests": 2}
  }
}
```

### Fields

Top level, every model:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | `gen-<created>-<20 chars>` |
| `object` | string | Always `chat.completion` |
| `created` | int | Unix seconds |
| `model` | string | The id that was asked for |
| `provider` | string | `OpenAI`, `Perplexity`, `Google` |
| `system_fingerprint` | null | Always null on these three |
| `service_tier` | string or null | `default` for OpenAI and Google, null for Perplexity |
| `choices` | array | Exactly one element |
| `usage` | object | Token counts and cost |

`choices[0]`:

| Field | Type | Description |
|-------|------|-------------|
| `index` | int | `0` |
| `logprobs` | null | |
| `finish_reason` | string | `stop` |
| `native_finish_reason` | string | Vendor's own word: `completed` (OpenAI), `stop` (Perplexity), `STOP` (Google) |
| `message` | object | The answer |

`choices[0].message`:

| Field | Type | Description |
|-------|------|-------------|
| `role` | string | `assistant` |
| `content` | string | The answer, markdown |
| `refusal` | null | |
| `reasoning` | string or null | Reasoning summary on GPT, null elsewhere |
| `reasoning_details` | array | GPT and Gemini only; absent on Sonar |
| `annotations` | array of object | One `url_citation` per cited page; **absent** on an image read |

`annotations[]`:

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Always `url_citation` |
| `url_citation.url` | string | The cited page |
| `url_citation.title` | string | Page title, or bare domain on Gemini |
| `url_citation.start_index` | int | Byte offset into `content` |
| `url_citation.end_index` | int | Byte offset into `content` |

There is no `content` snippet key inside `url_citation` on any of the three
models.

`usage`, every model: `prompt_tokens`, `completion_tokens`, `total_tokens`
(ints), `cost` (float, dollars), `is_byok` (bool), plus the three `_details`
objects shown above. `server_tool_use_details.web_search_requests` appears
only when a search ran.

### Web plugin behaviour per model

**`openai/gpt-5.6-luna`, `plugins: [{"id": "web", "engine": "native"}]`** —
OpenAI's own web search. Two citations for the query; each `url` is the real
page with `utm_source=openai` appended; `title` is the page's title; the span
covers the `([domain](url))` marker GPT appends after the sentence it
supports. `usage.prompt_tokens` runs to ~21k because the search results are
counted as prompt. `message.reasoning` carries a summary string.

**`perplexity/sonar`, no plugins** — Sonar searches on its own. Twenty
citations for the query, mostly listicles; `content` refers to them with
`[n]` markers where `n` is the 1-based position in `annotations`; every
`start_index` and `end_index` is `0`. Sending the web plugin as well was not
needed and was not captured.

**`google/gemini-3.5-flash-lite`, `plugins: [{"id": "web", "engine": "native"}]`** —
Google Search grounding. Ten citations; every `url` is a
`vertexaisearch.cloud.google.com/grounding-api-redirect/<opaque>` link that
resolves to the page on request, and `title` is the page's bare domain
(`innowise.com`, `salesforce.com`). Spans cover whole sentences or
paragraphs. A hook that wants the cited domain reads `title`, not `url`.

### Image reading

`content` as parts, one text and one `image_url`. No `plugins`.

```bash
curl https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer <key>" -H "Content-Type: application/json" \
  -d '{"model": "openai/gpt-5.6-luna",
       "messages": [{"role": "user", "content": [
         {"type": "text", "text": "Read the advertisement in this image. Reply with only the words visible in the ad, headline first, in reading order. Reply NONE when there is no text."},
         {"type": "image_url", "image_url": {"url": "https://tpc.googlesyndication.com/archive/simgad/15504638168199775183"}}
       ]}]}'
```

**Example Response** (trimmed):
```json
{
  "id": "gen-1789528712-a3mjVz0aJU7zn2HaGcMo",
  "object": "chat.completion",
  "created": 1789528712,
  "model": "openai/gpt-5.6-luna",
  "provider": "OpenAI",
  "system_fingerprint": null,
  "service_tier": "default",
  "choices": [
    {
      "index": 0,
      "logprobs": null,
      "finish_reason": "stop",
      "native_finish_reason": "completed",
      "message": {
        "role": "assistant",
        "content": "Vacation Apartments &  \nVillas - Luxury Second...  \nWith August co-ownership, enjoy up to  \nvacation in 5 European destinations.  \nOur Current Homes  \nVisit Our Website Today  \nAugust Collection  \nwww.augustcollections.com/",
        "refusal": null,
        "reasoning": "...",
        "reasoning_details": [{"type": "reasoning.summary", "summary": "...", "format": "openai-responses-v1", "index": 0}]
      }
    }
  ],
  "usage": {
    "prompt_tokens": 425,
    "completion_tokens": 571,
    "total_tokens": 996,
    "cost": 0.0007702,
    "is_byok": false,
    "prompt_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0, "audio_tokens": 0, "video_tokens": 0},
    "cost_details": {"upstream_inference_cost": 0.0007702, "upstream_inference_prompt_cost": 8.5e-05, "upstream_inference_completions_cost": 0.0006852},
    "completion_tokens_details": {"reasoning_tokens": 516, "image_tokens": 0, "audio_tokens": 0}
  }
}
```

The message carries no `annotations` key at all. Lines end in two spaces
plus a newline (markdown line breaks). The preview came from SerpApi's
`google_ads_transparency_center` engine with `text=hubspot.com`, which
matches ads *mentioning* that text, not ads *by* that advertiser; the real
connector asks by `advertiser_id`.

## Error Responses

| HTTP Status | Meaning |
|-------------|---------|
| 400 | Unknown model id, malformed body |
| 401 | Missing or invalid bearer |
| 402 | Insufficient credits |
| 429 | Rate limited by OpenRouter or the upstream vendor |
| 502 | Upstream vendor failed |

Unknown model:

```json
{
  "error": {
    "message": "openai/gpt-0-nonexistent is not a valid model ID",
    "code": 400
  },
  "user_id": "user_36SUeAZoYG5UpjlBHR0YZ0FqC10"
}
```

Only 400 and 401 were captured; the others are from the vendor's docs.

## Notes

- The web plugin's `max_results` bounds pages fetched, not citations
  returned: GPT cited 2, Gemini 10, Sonar 20 (no plugin)
- `start_index`/`end_index` are offsets into `content`; the connectors do not
  read them, only `content` and each `url_citation.url` in order
- A `:online` model suffix is OpenRouter's shorthand for the same web plugin;
  the stand-in accepts it and strips it, the real API was not called with it
- Vendor keys never appear in the response

## What the stand-in leaves out

- `message.reasoning_details` and the GPT `reasoning` summary string
  (`reasoning` is always null)
- `usage.prompt_tokens_details`, `usage.cost_details`,
  `usage.completion_tokens_details`, `usage.server_tool_use_details`
- Sonar's `[n]` markers in `content` and its zero spans; the stand-in gives
  every model a span over the sentence that names the cited company
- GPT's `([domain](url))` markers in `content`; the stand-in keeps the
  `utm_source=openai` on GPT urls and the redirect url plus bare-domain title
  on Gemini
- `user_id` on the 400 body is a fixed placeholder
- The stand-in answers an image read with the text of the creative whose
  `spy_ads` preview matches the url, and for any other url with a text
  derived from the url's last path segment; the real model reads the pixels
- Any bearer passes; the real API answers 401 `User not found.` to a wrong
  key
- Streaming, tool calls, multi-turn, `max_tokens`, `temperature`

## Reference

- [Chat completions](https://openrouter.ai/docs/api-reference/chat-completion)
- [Web search plugin](https://openrouter.ai/docs/features/web-search)
- [Annotations](https://openrouter.ai/docs/api-reference/overview#annotations)
- [Image inputs](https://openrouter.ai/docs/features/multimodal/images)
- [Errors](https://openrouter.ai/docs/api-reference/errors)
- [Perplexity Sonar sunset](https://docs.perplexity.ai/changelog)
