# AI Answers — AI Visibility Tracker

## Overview

An AI-visibility tracker asks the same question of several answer engines on a schedule and records which brands each one named and which URL it cited. OS uses it to watch whether we are in the answer at all: the Studio AI-answers view is a prompt × engine grid of who was named, and our own row is usually empty.

There is no standard API for this. Profound, Peec AI and Otterly each sell the category with their own shape, none of them public enough to replicate faithfully. So this contract is the one the open repo ships: the smallest honest surface that carries the reading a tracker produces. A connector written against it will need rewriting against whichever vendor a company actually buys — the reading it produces will not.

- **Category:** Competitors
- **Production Base URL:** vendor-specific; there is no standard one
- **Mock Base URL:** `http://mock:8100/answers` (from the host: `http://localhost:9192/answers`)
- **API Version:** v1
- **Response Format:** JSON

## Authentication

Bearer token, through the shared `require_bearer` helper in `helpers.py`.

```
Authorization: Bearer mock_ai_answers_token
```

Any non-empty bearer token is accepted. A missing or malformed one answers `401` with FastAPI's `detail` body rather than this vendor's envelope, because the mechanism check is the shared helper; every other error uses the envelope below.

---

## Endpoints

### 1. Mentions for one prompt on one engine

```
GET /v1/mentions
```

One call is one reading: a prompt, an engine, and a row for every brand being watched — ours and the three competitors — whether or not it was named.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prompt` | string | **required** | One of the tracked prompts |
| `engine` | string | **required** | `chatgpt`, `perplexity`, `gemini` or `aio` |

**Example request:**

```bash
curl -G "http://localhost:9192/answers/v1/mentions" \
  -H "Authorization: Bearer mock_ai_answers_token" \
  --data-urlencode "prompt=ugc ads without creators" \
  --data-urlencode "engine=chatgpt"
```

**Example response (200):**

```json
{
  "prompt": "ugc ads without creators",
  "engine": "chatgpt",
  "checked_at": "2026-09-14T05:45:00Z",
  "mentions": [
    {
      "brand": "Digital Workers",
      "domain": "hiredigitalworkers.com",
      "mentioned": "yes",
      "cited_url": "https://hiredigitalworkers.com/ugc",
      "rank": 3
    },
    {
      "brand": "Vidora",
      "domain": "vidora.ai",
      "mentioned": "yes",
      "cited_url": "https://vidora.ai/blog/what-a-creator-brief-costs",
      "rank": 1
    },
    {
      "brand": "Clipwise",
      "domain": "clipwise.io",
      "mentioned": "no",
      "cited_url": "",
      "rank": 0
    },
    {
      "brand": "Avatarly",
      "domain": "avatarly.com",
      "mentioned": "yes",
      "cited_url": "https://avatarly.com/how-it-works",
      "rank": 2
    }
  ],
  "next": null
}
```

**Mention fields:**

| Field | Type | Description |
|-------|------|-------------|
| `brand` | string | The brand's name as the tracker knows it |
| `domain` | string | Its domain, which is how OS folds it against the other sources |
| `mentioned` | string | `yes` or `no`, not a boolean — trackers report a reading, not a fact |
| `cited_url` | string | The URL the answer linked to; empty string when not mentioned |
| `rank` | integer | 1-based position in the answer; `0` when not mentioned |

A brand that was not named still gets a row. The absence is the measurement, and a connector that only stored the hits would have nothing to draw an empty cell from.

`checked_at` is frozen, so the same prompt and engine answer byte-identically every time.

---

## Pagination

None. `next` is always `null`. It is in the shape because every vendor in this category paginates something, and a connector that ignores the key from the start will break the first time it meets one that does.

---

## Error Responses

### Missing or malformed bearer token (401)

```json
{ "detail": "Unauthorized" }
```

### Untracked prompt (404)

```json
{
  "error": {
    "code": "prompt_not_tracked",
    "message": "Prompt 'how much does it cost' is not in the tracked set."
  }
}
```

### Unsupported engine (404)

```json
{
  "error": {
    "code": "engine_not_supported",
    "message": "Engine 'copilot' is not one of chatgpt, perplexity, gemini, aio."
  }
}
```

### Missing required parameter (422)

`prompt` and `engine` are required; the mock refuses their absence with FastAPI's validation body.

---

## What the connector stores

A mention row does not name the prompt or the engine it came from — those sit one level up, on the envelope. The connector flattens `mentions` and carries them down, under the same leading-underscore convention as the other competitor sources:

| Key | From |
|-----|------|
| `_prompt` | `prompt` |
| `_engine` | `engine` |
| `_checked_on` | the date part of `checked_at` |

The stored `source_id` is `<prompt>|<engine>|<brand>|<date>` — four rows per call, twelve calls, forty-eight rows a day. Captured in `app/backend/fixtures/mock/ai_answers/mentions.json`.

---

## What the mock simplifies

- Three prompts × four engines = twelve readings, four brands each. Any other prompt or engine is a 404.
- The picture is fixed, not generated, because it is the thing the Studio view is for: Vidora is named in nine of the twelve, Clipwise in five, Avatarly in four, and we are named twice — both on `ugc ads without creators`, on chatgpt and perplexity only, and never on `aio`. The `aio` reading of `how do i make video ads with ai` names nobody at all, which is the empty-answer case a connector has to survive.
- No answer text, no citation list beyond one URL per brand, no sentiment, no share-of-voice rollup, no competitor discovery. A real tracker returns the full answer and lets you re-read it; this returns the reading only.
- No scheduling, no run history, no per-run cost. One GET is one reading.
- `checked_at` is frozen rather than tracking the clock.

---

## Reference

- [Profound](https://www.tryprofound.com/) -- Answer-engine visibility, the largest of the category
- [Peec AI](https://peec.ai/) -- Prompt-level brand tracking across engines
- [Otterly.AI](https://otterly.ai/) -- Search-prompt monitoring including Google AI Overviews
