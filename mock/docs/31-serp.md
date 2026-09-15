# SerpApi — Google Search Engine

## Overview

SerpApi runs a Google search on request and returns the result page as JSON. OS uses it to keep a dated ranking row for every tracked keyword: where our domain sits, where each competitor sits, and who else is on the page. The Studio search view is a query over those rows.

- **Category:** Competitors
- **Production Base URL:** `https://serpapi.com`
- **Mock Base URL:** `http://mock:8100/serp` (from the host: `http://localhost:9192/serp`)
- **Engine:** `google`
- **Response Format:** JSON

### Why `/serp` and not `/serpapi`

`30-google-ads-transparency.md` is the same vendor and already holds `/serpapi`. Both engines live at the same path — `GET /search`, selected by the `engine` parameter — and one FastAPI app cannot mount two routers on the same path without one shadowing the other. So the mock gives each engine its own prefix. Nothing is lost: in production the two connectors differ only in their base URL, which is a per-source setting either way.

## Authentication

An API key passed as a **query parameter**, the same mechanism as the transparency engine.

```
?api_key=mock_serpapi_key
```

Any non-empty `api_key` is accepted by the mock. The check is inline rather than through a helper in `helpers.py`, because the body SerpApi answers with is its own.

---

## Endpoints

### 1. Search

```
GET /search
```

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | string | **required** | SerpApi key |
| `engine` | string | **required** | Must be `google`; anything else is refused |
| `q` | string | **required** | The keyword to search |
| `location` | string | `United States` | Where the search is run from |
| `num` | integer | — | Results to return, 1-100; the mock holds ten |

**Example request:**

```bash
curl -G "https://serpapi.com/search" \
  --data-urlencode "api_key=mock_serpapi_key" \
  --data-urlencode "engine=google" \
  --data-urlencode "q=ai ugc ads" \
  --data-urlencode "location=United States" \
  --data-urlencode "num=10"
```

**Example response (200):**

```json
{
  "search_metadata": {
    "status": "Success",
    "created_at": "2026-09-14 05:42:11 UTC"
  },
  "search_parameters": {
    "engine": "google",
    "q": "ai ugc ads",
    "location_requested": "United States",
    "location_used": "United States",
    "google_domain": "google.com",
    "device": "desktop",
    "num": 10
  },
  "organic_results": [
    {
      "position": 1,
      "title": "Vidora — video ads from a product URL",
      "link": "https://vidora.ai/",
      "displayed_link": "https://vidora.ai",
      "snippet": "Paste a product URL. Vidora reads the page, writes three scripts in your voice, picks a presenter and renders a captioned ad for each one. The first cut ..."
    },
    {
      "position": 9,
      "title": "Digital Workers — AI video ads, made by an operator not a studio",
      "link": "https://hiredigitalworkers.com/",
      "displayed_link": "https://hiredigitalworkers.com",
      "snippet": "We run the tool, you approve the ad. Digital Workers writes, renders and ships video ads for brands that do not want another seat to manage."
    }
  ]
}
```

**Organic result fields:**

| Field | Type | Description |
|-------|------|-------------|
| `position` | integer | 1-based rank on the page |
| `title` | string | The result's link text |
| `link` | string | The absolute URL |
| `displayed_link` | string | Google's breadcrumb form, `https://domain › path` |
| `snippet` | string | The excerpt Google shows, truncated with ` ...` |

`created_at` is frozen. The same keyword answers byte-identically every time, so a capture can be compared against a later one without the timestamp moving underneath it.

---

## Pagination

None. Ten results is the whole page for every keyword, and the mock ignores `start`. Real SerpApi paginates with `start` and reports `serpapi_pagination`; a tracker that only wants the first page never sends it.

---

## Error Responses

### Missing or empty `api_key` (401)

```json
{
  "error": "Invalid API key. Your API key should be here: https://serpapi.com/manage-api-key"
}
```

### Wrong engine (400)

```json
{
  "error": "Unsupported `bing` engine."
}
```

### Untracked keyword (200)

SerpApi answers an empty result page with a body, not a status code:

```json
{
  "error": "Google hasn't returned any results for this query."
}
```

### Missing required parameter (422)

`engine` and `q` are required; the mock refuses their absence with FastAPI's validation body rather than SerpApi's.

---

## What the connector stores

`organic_results` is a list of rows that do not name the search they came from — the query lives in `search_parameters`, one level up. So the connector flattens the list and carries the request's subject onto each row before storing it, under the leading-underscore convention the Ad Library connector already uses for fields the vendor did not send:

| Key | From |
|-----|------|
| `_keyword` | `search_parameters.q` |
| `_engine` | `search_parameters.engine` |
| `_domain` | the host of `link` |
| `_checked_on` | the date part of `search_metadata.created_at` |

The stored `source_id` is `<keyword>|<engine>|<domain>|<date>`, which makes one row per keyword per domain per day and lets a re-run on the same day overwrite rather than duplicate. Captured in `app/backend/fixtures/mock/serp/organic_results.json`.

---

## What the mock simplifies

- Four keywords, ten results each. Anything else answers with the empty-results body.
- Rankings are fixed, not generated: Vidora leads the two hot keywords, our domain sits at #9 and #10 on those and at #2 on the long-tail `ai ads without a studio`. That contrast is the story the Studio search view tells, so it is written down rather than derived.
- Competitors' titles and snippets come from `COMPETITOR_PAGES` in `world.py`, so a result and the crawled page behind it agree. The filler domains are fictional tools and roundups that exist only in this module.
- No ads, no knowledge graph, no people-also-ask, no related searches, no local pack, no `serpapi_pagination`, no `search_information`. Only `organic_results`.
- `location` is echoed and otherwise ignored; every result is the US page.
- `created_at` is frozen at one moment rather than tracking the clock.

---

## Reference

- [SerpApi Google Search API](https://serpapi.com/search-api) -- Parameters and the full response shape
- [Organic results](https://serpapi.com/organic-results) -- Field-by-field description of an organic result
- [SerpApi errors](https://serpapi.com/search-api#api-examples) -- Status codes and the `error` body
