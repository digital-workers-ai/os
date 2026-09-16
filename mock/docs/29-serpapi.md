# SerpApi (Google Search, Google AI Overview, Google Ads Transparency Center)

## Overview

SerpApi is one HTTP endpoint, `GET /search.json`, that scrapes a Google surface
chosen by the `engine` parameter and returns it as JSON. Spy reads three
engines:

| Engine | What it returns | Read by |
|--------|-----------------|---------|
| `google` | Organic results for a query, with the AI Overview when Google shows one inline | `google_serp` |
| `google_ai_overview` | The AI Overview that a `google` search only handed out a `page_token` for | `google_serp` |
| `google_ads_transparency_center` | The creatives an advertiser is running, from Google's Ads Transparency Center | `google_ads_transparency` |

Everything below was observed against the real API on 2026-09-16 with the key
in `app/.env`; the request lines are the exact calls, the JSON is the real
answer trimmed. Where the stand-in departs from what was observed it says so.

## Base URL

```
https://serpapi.com
```

The stand-in mounts the same path under `/serpapi`; `/search` answers the same
as `/search.json`.

## Authentication

A private key on every request as the `api_key` query parameter. No header.

```
GET /search.json?engine=google&q=...&api_key=<key>
```

Without one, 401:

```json
{
  "error": "Invalid API key. Your API key should be here: https://serpapi.com/manage-api-key"
}
```

The stand-in accepts any non-empty `api_key`; the connectors send
`mock_serpapi_key`.

## Rate Limits

Plans carry a monthly search quota and an hourly throughput limit. Both answer
429 with the same one-key error body; the documented message for an exhausted
plan is `Your account has run out of searches.`. Cached searches (same query and
parameters within an hour) are free and do not count. The stand-in never
answers 429.

---

## Endpoints

### GET /search.json?engine=google

One page of Google results for a query.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `q` | string | — | Required. The search |
| `gl` | string | — | Country code, lowercase (`us`) |
| `hl` | string | — | Language code (`en`) |
| `num` | int | 10 | Results per page; Google may return fewer |
| `google_domain` | string | `google.com` | Which Google to ask |
| `device` | string | `desktop` | `desktop`, `tablet` or `mobile` |
| `start` | int | 0 | Offset for further pages |

**Example Request:**
```bash
curl "https://serpapi.com/search.json?engine=google&q=best+crm+for+small+business&gl=us&hl=en&num=10&api_key=<key>"
```

**Example Response** (trimmed; the archive host path is elided):
```json
{
  "search_metadata": {
    "id": "6aaa0a58d6eb722a0d170d41",
    "status": "Success",
    "json_endpoint": "https://serpapi.com/searches/.../6aaa0a58d6eb722a0d170d41.json",
    "markdown_endpoint": "https://serpapi.com/searches/.../6aaa0a58d6eb722a0d170d41.md",
    "pixel_position_endpoint": "https://serpapi.com/searches/.../6aaa0a58d6eb722a0d170d41.json_with_pixel_position",
    "created_at": "2026-09-16 03:17:44 UTC",
    "processed_at": "2026-09-16 03:17:44 UTC",
    "google_url": "https://www.google.com/search?q=best+crm+for+small+business&oq=best+crm+for+small+business&hl=en&gl=us&sourceid=chrome&ie=UTF-8",
    "raw_html_file": "https://serpapi.com/searches/.../6aaa0a58d6eb722a0d170d41.html",
    "total_time_taken": 0.56
  },
  "search_parameters": {
    "engine": "google",
    "q": "best crm for small business",
    "google_domain": "google.com",
    "hl": "en",
    "gl": "us",
    "device": "desktop"
  },
  "search_information": {
    "query_displayed": "best crm for small business",
    "total_results": 85,
    "time_taken_displayed": 0.14,
    "organic_results_state": "Results for exact spelling"
  },
  "related_questions": [
    {
      "question": "Will CRM be replaced by AI?",
      "type": "ai_overview",
      "page_token": "jcM4b3icHdBRboIwAADQ7DJ...",
      "serpapi_ai_overview_link": "https://serpapi.com/search.json?engine=google_ai_overview&page_token=jcM4b3icHdBRboIwAADQ7DJ...",
      "next_page_token": "eyJvbnMiOiIxMDA0MSIs...",
      "serpapi_link": "https://serpapi.com/search.json?device=desktop&engine=google_related_questions&google_domain=google.com&next_page_token=..."
    }
  ],
  "ai_overview": {
    "text_blocks": [
      {
        "type": "paragraph",
        "snippet": "The best CRM for small business is HubSpot CRM for free tools and inbound marketing, or Pipedrive for visual sales pipelines.",
        "snippet_highlighted_words": ["HubSpot CRM"]
      },
      {
        "type": "heading",
        "snippet": "Top CRM Options for Small Businesses"
      },
      {
        "type": "list",
        "list": [
          {"snippet": "HubSpot CRM: Best for startups and teams wanting a strong free-forever tier (supports two users) with easy scaling into marketing and service hubs."},
          {"snippet": "Pipedrive: Best for sales-focused teams that need an intuitive, visual drag-and-drop pipeline to track deals fast."},
          {"snippet": "Zoho CRM: Best for budget-conscious teams wanting deep customization, an all-in-one ecosystem, and a free tier for up to three users."}
        ]
      }
    ],
    "references": [
      {
        "link": "https://www.uschamber.com/co/start/strategy/low-cost-crm-tools",
        "source": "uschamber.com",
        "index": 0
      },
      {
        "title": "10 Free or Low-Cost CRM Tools for Small Businesses",
        "link": "https://www.uschamber.com/co/start/strategy/low-cost-crm-tools",
        "snippet": "HubSpot: Best free CRM tools for startups. HubSpot offers a free CRM packed with features for managing customers and sales. It supports two users and 1,000 contact...",
        "source": "US Chamber",
        "thumbnail": "https://encrypted-tbn3.gstatic.com/images?q=tbn:...",
        "source_icon": "https://encrypted-tbn2.gstatic.com/faviconV2?url=https://www.uschamber.com&client=AIM&size=128&type=FAVICON&fallback_opts=TYPE,SIZE,URL",
        "index": 9
      }
    ]
  },
  "organic_results": [
    {
      "position": 1,
      "title": "CRM For Small Business (Your Complete Guide)",
      "link": "https://www.salesforce.com/crm/crm-for-small-business/",
      "redirect_link": "https://www.google.com/url?sa=t&source=web&rct=j&opi=89978449&url=...",
      "displayed_link": "https://www.salesforce.com › crm › crm-for-small-busi...",
      "favicon": "https://serpapi.com/images/i/....webp",
      "snippet": "Salesforce CRM is the best for small businesses Small businesses need a CRM solution that addresses existing pain points, improves current sales operations,",
      "snippet_highlighted_words": ["Salesforce CRM"],
      "about_this_result": {
        "source": {"description": "...", "source_info_link": "https://www.salesforce.com/crm/crm-for-small-business/", "icon": "https://serpapi.com/images/i/....webp"},
        "languages": ["en"],
        "regions": ["US"]
      },
      "about_page_link": "https://www.google.com/search?q=About+https://www.google.com/goto?url=...&tbm=ilp",
      "about_page_serpapi_link": "https://serpapi.com/search.json?engine=google_about_this_result&google_domain=google.com&q=...",
      "source": "Salesforce"
    },
    {
      "position": 8,
      "title": "The Best Small Business CRM Software for 2026",
      "link": "https://www.pcmag.com/picks/the-best-small-business-crm-software",
      "redirect_link": "https://www.google.com/url?...",
      "displayed_link": "https://www.pcmag.com › ... › CRM Software",
      "favicon": "https://serpapi.com/images/i/....png",
      "date": "Jul 22, 2026",
      "snippet": "Our Top Tested Picks · Bigin by Zoho CRM · Freshsales · Salesforce Starter Suite · HoneyBook · Less Annoying CRM · Pipedrive CRM · The Best CRM ...",
      "snippet_highlighted_words": ["Bigin by Zoho CRM"],
      "sitelinks": {"inline": [{"title": "Best For Salesforce Users", "link": "https://www.pcmag.com/picks/the-best-small-business-crm-software#:~:text=..."}]},
      "about_this_result": {"source": {"description": "...", "source_info_link": "...", "icon": "..."}, "languages": ["en"], "regions": ["US"]},
      "about_page_link": "...",
      "about_page_serpapi_link": "...",
      "source": "PCMag",
      "read_more_link": "https://www.pcmag.com/picks/the-best-small-business-crm-software#:~:text=..."
    }
  ],
  "related_searches": [
    {"block_position": 1, "query": "Best crm for small business reddit", "link": "https://www.google.com/search?...", "serpapi_link": "https://serpapi.com/search.json?...&q=Best+crm+for+small+business+reddit"}
  ],
  "pagination": {"current": 1, "next": "https://www.google.com/search?...&start=10", "other_pages": {"2": "...", "3": "..."}},
  "serpapi_pagination": {"current": 1, "next_link": "https://serpapi.com/search.json?...&start=10", "next": "https://serpapi.com/search.json?...&start=10", "other_pages": {"2": "...", "3": "..."}}
}
```

Nine organic results came back for `num=10`; Google decides the count. `num`
is not echoed in `search_parameters`.

**`organic_results[]`** — one object per blue link:

| Field | Type | Always | Description |
|-------|------|--------|-------------|
| `position` | int | yes | 1-based rank on the page |
| `title` | string | yes | Link text |
| `link` | string | yes | Destination URL |
| `displayed_link` | string | yes | The breadcrumb Google shows (`https://host › path › ...`) |
| `snippet` | string | yes | The description under the link |
| `source` | string | yes | Site name as Google labels it (`Salesforce`, `PCMag`) |
| `redirect_link` | string | yes | Google's tracking redirect |
| `favicon` | string | yes | Icon URL, hosted by SerpApi |
| `snippet_highlighted_words` | array of string | yes | Bold fragments of the snippet |
| `about_this_result` | object | yes | `source.description`, `source.source_info_link`, `source.icon`, `languages[]`, `regions[]` |
| `about_page_link` | string | yes | Google's "about this result" page |
| `about_page_serpapi_link` | string | yes | Same, through SerpApi's `google_about_this_result` engine |
| `date` | string | no | `Jul 22, 2026` when Google dates the page |
| `read_more_link` | string | no | Text-fragment link into the page |
| `sitelinks` | object | no | `inline[]` of `{title, link}` |

**`ai_overview`** — one of three shapes, or absent when Google shows no
overview for the query:

1. Inline: `{"text_blocks": [...], "references": [...]}` as above.
2. Deferred: Google rendered the overview through a second request, so the
   search carries only a token for it:

```json
{
  "ai_overview": {
    "page_token": "rWmjgXictZPdkqI4FMcv90nWvWBUtO0e7SpqKiBqHL8ifuENhRADgnwFjHo377JPtU...",
    "serpapi_link": "https://serpapi.com/search.json?engine=google_ai_overview&page_token=rWmjgXictZPdkqI4FMcv90nWvWBUtO0e7SpqKiBqHL8ifuENhRADgnwFjHo377JPtU..."
  }
}
```

   The token expires within minutes of the search (the docs say one on the AI
   Overview page and four on the Google Search page); fetch it immediately.
3. Failed: `{"ai_overview": {"error": "Can't generate an AI overview right now. Try again later."}}`.

Shapes 2 and 3 are from SerpApi's documentation; the real call today came
back inline.

**`ai_overview.text_blocks[]`** — the overview as ordered blocks. Every block
has `type`; the rest depends on it:

| `type` | Keys | Notes |
|--------|------|-------|
| `paragraph` | `snippet`, `snippet_highlighted_words?`, `reference_indexes?` | Plain text |
| `heading` | `snippet`, `reference_indexes?` | Section title |
| `list` | `list[]` of `{title?, snippet, reference_indexes?, snippet_links?, list?}` | Bullets; a bullet can carry a nested `list` |
| `expandable` | `title`, `subtitle?`, `text_blocks[]` | A collapsed section; `text_blocks` has this same structure |
| `table` | `table` (array of array of string), `formatted?` | First row is the header |
| `comparison` | `product_labels[]`, `comparison[]` of `{feature, values[]}` | Product tables |
| `top_stories` | `top_stories[]` of `{link, ...}` | News cards |

`reference_indexes` are integer offsets into `references`. `snippet_links` is
an array of `{text, link}` for inline links in the snippet.

**`ai_overview.references[]`** — the cited pages. Two shapes appeared in one
response: `{link, source, index}` for a bare citation and
`{title, link, snippet, source, thumbnail?, source_icon?, index}` for a rendered
card, and the same URL can appear in both, so `link` values repeat.

### GET /search.json?engine=google_ai_overview

The AI Overview a `google` search deferred.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page_token` | string | — | Required. `ai_overview.page_token` from the search |

**Example Request:**
```bash
curl "https://serpapi.com/search.json?engine=google_ai_overview&page_token=jcM4b3icHdBRboIwAADQ7DJ...&api_key=<key>"
```

The token used here came from `related_questions[0].page_token` of the search
above, because that search answered its own overview inline; the response
shape is the same either way.

**Example Response:**
```json
{
  "search_metadata": {
    "id": "6aaa0ad9f96561deb0ad6dd6",
    "status": "Success",
    "json_endpoint": "https://serpapi.com/searches/.../6aaa0ad9f96561deb0ad6dd6.json",
    "markdown_endpoint": "https://serpapi.com/searches/.../6aaa0ad9f96561deb0ad6dd6.md",
    "created_at": "2026-09-16 03:19:53 UTC",
    "processed_at": "2026-09-16 03:19:53 UTC",
    "google_ai_overview_url": "https://www.google.com/async/callback:6761?fc=EssBCowBQUppVDR0S0tt...",
    "raw_html_file": "https://serpapi.com/searches/.../6aaa0ad9f96561deb0ad6dd6.html",
    "total_time_taken": 2.01
  },
  "search_parameters": {
    "engine": "google_ai_overview",
    "page_token": "jcM4b3icHdBRboIwAADQ7DJ..."
  },
  "ai_overview": {
    "text_blocks": [
      {
        "type": "paragraph",
        "snippet": "No, AI will not replace CRM systems; instead, it is transforming them into ...",
        "snippet_highlighted_words": ["No"]
      },
      {"type": "heading", "snippet": "How AI is changing CRM"},
      {
        "type": "list",
        "list": [
          {"snippet": "Automation: AI handles data entry, lead scoring and follow-up scheduling."},
          {"snippet": "Reuters reports on ...", "snippet_links": [{"text": "Reuters", "link": "https://www.reuters.com/plus/raising-your-profile-worldwide/the-future-of-crm-whats-changing-and-why-it-matters"}]}
        ]
      },
      {"type": "top_stories", "top_stories": [{"link": "https://..."}]}
    ],
    "references": [
      {
        "title": "Why AI Will Not Replace Your CRM — And Why That's Actually the Point",
        "link": "https://www.linkedin.com/pulse/why-ai-replace-your-crm-thats-actually-point-amit-gupta-fjoyc",
        "snippet": "The manual CRM that requires your team to act like data entry clerks is dying — but what's replacing it isn't a raw database. It's a smarter CRM where AI does the ...",
        "source": "LinkedIn",
        "thumbnail": "https://encrypted-tbn0.gstatic.com/images?q=tbn:...",
        "source_icon": "https://encrypted-tbn2.gstatic.com/faviconV2?url=https://www.linkedin.com&client=AIM&size=128&type=FAVICON&fallback_opts=TYPE,SIZE,URL",
        "index": 0
      }
    ]
  }
}
```

No `search_information`, no organic results: the three top-level keys above
are the whole response. `search_metadata` carries `google_ai_overview_url`
where a search carries `google_url`, and no `pixel_position_endpoint`.

### GET /search.json?engine=google_ads_transparency_center

The creatives one advertiser is running, or the creatives matching a free-text
search, from the Ads Transparency Center.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `advertiser_id` | string | — | `AR` + 20 digits, from the Transparency Center URL; several ids comma-separated |
| `text` | string | — | Free-text search, typically a domain; either this or `advertiser_id` is required |
| `num` | int | 40 | Page size |
| `next_page_token` | string | — | `serpapi_pagination.next_page_token` from the previous page |
| `region` | string | anywhere | Numeric region code (`2840` is the US) |
| `platform` | string | all | `PLAY`, `MAPS`, `SEARCH`, `SHOPPING`, `YOUTUBE` |
| `creative_format` | string | all | `text`, `image`, `video` |
| `start_date`, `end_date` | string | — | `YYYYMMDD` |
| `political_ads` | bool | false | Political creatives only; needs `region` |
| `get_advertiser` | bool | false | Adds an `advertiser` block (legal name, country) with one extra request; single id only |

**Example Request** (discovering an advertiser id from a domain):
```bash
curl "https://serpapi.com/search.json?engine=google_ads_transparency_center&text=hubspot.com&num=10&api_key=<key>"
```

**Example Response:**
```json
{
  "search_metadata": {
    "id": "6aaa0a10ab28c664cc7add8b",
    "status": "Success",
    "json_endpoint": "https://serpapi.com/searches/.../6aaa0a10ab28c664cc7add8b.json",
    "markdown_endpoint": "https://serpapi.com/searches/.../6aaa0a10ab28c664cc7add8b.md",
    "created_at": "2026-09-16 03:16:32 UTC",
    "processed_at": "2026-09-16 03:16:32 UTC",
    "google_ads_transparency_center_url": "https://adstransparency.google.com?region=anywhere&domain=hubspot.com",
    "raw_html_file": "https://serpapi.com/searches/.../6aaa0a10ab28c664cc7add8b.html",
    "prettify_html_file": "https://serpapi.com/searches/.../6aaa0a10ab28c664cc7add8b.prettify",
    "total_time_taken": 4.32
  },
  "search_parameters": {
    "engine": "google_ads_transparency_center",
    "text": "hubspot.com",
    "num": "10"
  },
  "search_information": {
    "total_results": 4000
  },
  "ad_creatives": [
    {
      "advertiser_id": "AR10072600183532683265",
      "advertiser": "Hubspot, Inc.",
      "ad_creative_id": "CR06609143572560084993",
      "format": "text",
      "target_domain": "hubspot.com",
      "image": "https://tpc.googlesyndication.com/archive/simgad/11373552786331311574",
      "width": 348,
      "height": 451,
      "total_days_shown": 1540,
      "first_shown": 1656541882,
      "last_shown": 1789525101,
      "details_link": "https://adstransparency.google.com/advertiser/AR10072600183532683265/creative/CR06609143572560084993?region=anywhere&domain=hubspot.com",
      "serpapi_details_link": "https://serpapi.com/search.json?advertiser_id=AR10072600183532683265&creative_id=CR06609143572560084993&engine=google_ads_transparency_center_ad_details"
    },
    {
      "advertiser_id": "AR10072600183532683265",
      "advertiser": "Hubspot, Inc.",
      "ad_creative_id": "CR08500885884000796673",
      "format": "video",
      "link": "https://displayads-formats.googleusercontent.com/ads/preview/content.js?client=ads-integrity-transparency&obfuscatedCustomerId=7615749964&creativeId=762393471498&uiFeatures=12,54&adGroupId=179898961377&versionId=11&assets=...&sig=...&htmlParentId=fletch-render-...&responseCallback=fletchCallback...",
      "target_domain": "hubspot.com",
      "total_days_shown": 409,
      "first_shown": 1752177946,
      "last_shown": 1789524935,
      "details_link": "https://adstransparency.google.com/advertiser/AR10072600183532683265/creative/CR08500885884000796673?region=anywhere&domain=hubspot.com",
      "serpapi_details_link": "https://serpapi.com/search.json?advertiser_id=AR10072600183532683265&creative_id=CR08500885884000796673&engine=google_ads_transparency_center_ad_details"
    },
    {
      "advertiser_id": "AR10072600183532683265",
      "advertiser": "Hubspot, Inc.",
      "ad_creative_id": "CR07984100738747858945",
      "format": "image",
      "target_domain": "hubspot.com",
      "image": "https://tpc.googlesyndication.com/archive/simgad/15529968583071394590",
      "total_days_shown": 91,
      "first_shown": 1781709978,
      "last_shown": 1789524559,
      "details_link": "https://adstransparency.google.com/advertiser/AR10072600183532683265/creative/CR07984100738747858945?region=anywhere&domain=hubspot.com",
      "serpapi_details_link": "https://serpapi.com/search.json?advertiser_id=AR10072600183532683265&creative_id=CR07984100738747858945&engine=google_ads_transparency_center_ad_details"
    }
  ],
  "serpapi_pagination": {
    "next_page_token": "CgoAP7zmkb+qiiU7EhDnYmf4AQgKB9NjyjEAAAAAGgn8+Go9+JCLXJQ=",
    "next": "https://serpapi.com/search.json?engine=google_ads_transparency_center&next_page_token=CgoAP7zmkb%2BqiiU7EhDnYmf4AQgKB9NjyjEAAAAAGgn8%2BGo9%2BJCLXJQ%3D&num=10&text=hubspot.com"
  }
}
```

The same call with `advertiser_id=AR10072600183532683265&num=20` answers the
same five top-level keys; the creatives then carry no `target_domain`,
`details_link` ends at `?region=anywhere`, `search_parameters` is
`{engine, advertiser_id, num}` and `search_information.total_results` was
`3000`. Ids seen today, all from the `text` search on the company domain:

| Company | `text` | `advertiser_id` | `advertiser` |
|---------|--------|-----------------|--------------|
| HubSpot | `hubspot.com` | `AR10072600183532683265` | `Hubspot, Inc.` |
| Zoho CRM | `zoho.com` | `AR07034216898162065409` | `Zoho Corporation Pvt. Ltd.` |
| Freshsales | `freshworks.com` | `AR03035893441289519105` | `Freshworks Inc.` |

**`ad_creatives[]`** — one object per creative; the keys depend on `format`:

| Field | Type | `text` | `image` | `video` | Description |
|-------|------|--------|---------|---------|-------------|
| `advertiser_id` | string | yes | yes | yes | `AR` + 20 digits |
| `advertiser` | string | yes | yes | yes | Legal name as registered |
| `ad_creative_id` | string | yes | yes | yes | `CR` + 20 digits |
| `format` | string | yes | yes | yes | `text`, `image` or `video` |
| `target_domain` | string | text search only | text search only | text search only | The domain the search matched |
| `image` | string | yes | yes | — | Preview render, `tpc.googlesyndication.com/archive/simgad/...` |
| `width`, `height` | int | yes | sometimes | — | Pixel size of the preview; image creatives came both with and without |
| `link` | string | — | — | yes | Preview player URL on `displayads-formats.googleusercontent.com` |
| `total_days_shown` | int | yes | yes | yes | Days the creative has run |
| `first_shown` | int | yes | yes | yes | Unix seconds |
| `last_shown` | int | yes | yes | yes | Unix seconds |
| `details_link` | string | yes | yes | yes | Transparency Center page for the creative |
| `serpapi_details_link` | string | yes | yes | yes | The `google_ads_transparency_center_ad_details` call for it |

No creative carries its copy; `image` is a rendered preview and video
creatives have no still at all.

## Pagination

Only the Ads Transparency engine paginates for Spy:

```json
{
  "serpapi_pagination": {
    "next_page_token": "CgoAP7zmkb+8Cn9nEhBN9OAx8WUa+Lu7p4IAAAAAGgn8+Go9+BzrD98=",
    "next": "https://serpapi.com/search.json?advertiser_id=AR10072600183532683265&engine=google_ads_transparency_center&next_page_token=CgoAP7zmkb%2B8Cn9nEhBN9OAx8WUa%2BLu7p4IAAAAAGgn8%2BGo9%2BBzrD98%3D&num=20"
  }
}
```

- Pass `next_page_token` with the previous page's value, same other params
- No `serpapi_pagination` key means the last page
- `search_information.total_results` is Google's rounded estimate
  (`3000`, `4000`, `5000`, `20000` today), not the exact count
- The stand-in's token is the base64 offset the shared `token_paginate` helper
  uses, and `total_results` is the exact count

The `google` engine pages with `start` (`serpapi_pagination.next` above);
Spy reads the first page only.

## Error Responses

| HTTP Status | Meaning |
|-------------|---------|
| 400 | Missing or unsupported parameter |
| 401 | No valid `api_key` |
| 403 | The account behind the key cannot make this request |
| 404 | No such route |
| 410 | An archived search that has been deleted |
| 429 | Hourly throughput limit, or the plan is out of searches |
| 500, 503 | SerpApi's side |

Every error is the same one-key body. Observed today:

```json
{"error": "Invalid API key. Your API key should be here: https://serpapi.com/manage-api-key"}
{"error": "Missing query `q` parameter."}
{"error": "Missing query `page_token` parameter."}
{"error": "Missing query `advertiser_id` parameter."}
{"error": "Unsupported `google_nope` search engine."}
```

The first is 401, the rest 400. A search that succeeds with nothing to show is
200 with `search_metadata.status` still `Success` and a top-level
`"error": "Google hasn't returned any results for this query."` beside the
metadata and parameters (from SerpApi's documentation; not hit today).

## Notes

- `search_parameters` echoes the request as strings: `num` came back as
  `"20"`, not `20`
- `first_shown` and `last_shown` are Unix seconds, integers; nothing on a
  creative is an ISO date
- Overview references repeat: the same URL showed up once bare and once as a
  card with different `index` values, so a citation count by `link` overcounts
- The overview `page_token` is single-use and short-lived; `related_questions`
  entries of `type: ai_overview` carry tokens of the same kind
- `text` search answers creatives from any advertiser whose ads match, not
  only the domain's owner; read `advertiser_id` off the creative rather than
  assuming one advertiser per response

### The stand-in

- `google` renders `search_metadata`, `search_parameters`,
  `search_information`, `organic_results` from `world.spy_serp(q)` (always
  ten), and `ai_overview` by `world.spy_ai_overview_mode(q)`: `inline` puts
  `world.spy_ai_overview(q)` in the response, `token` puts
  `{page_token, serpapi_link}` where the token is the url-safe base64 of the
  query and the link points back at the stand-in, `absent` omits the key
- `google_ai_overview` decodes the token to the query and answers
  `world.spy_ai_overview(q)`; a token that does not decode, or a query whose
  mode is `absent`, answers the documented failure shape
  `{"error": "Can't generate an AI overview right now. Try again later."}`
- `google_ads_transparency_center` answers `world.spy_ads(id)` for a known
  competitor id, paginated by `num` (default 40); `text` matches a competitor
  by domain, name or alias (case-insensitive) and adds `target_domain`, so
  an id can be discovered the way the real API allows; an unknown id or text
  answers the documented no-results shape
- Every response is deterministic from its parameters; timestamps are
  `world.SPY_ANCHOR` at noon UTC

## What the stand-in leaves out

Real keys the stand-in does not render, none of them read by Spy:

- `google`: `related_questions`, `related_searches`, `pagination`,
  `serpapi_pagination`; on each organic result `redirect_link`, `favicon`,
  `snippet_highlighted_words`, `about_this_result`, `about_page_link`,
  `about_page_serpapi_link`, `date`, `read_more_link`, `sitelinks`
- `ai_overview`: block types `expandable`, `table`, `comparison`,
  `top_stories`, and the `snippet_highlighted_words`, `snippet_links`
  keys; the `thumbnail` and `source_icon` keys on references; the bare
  `{link, source, index}` reference variant
- `google_ads_transparency_center`: `region`, `platform`, `creative_format`,
  `start_date`, `end_date`, `political_ads`, `get_advertiser` and the
  `advertiser` block; comma-separated ids; image creatives always carry
  `width` and `height`; `serpapi_pagination.next` points at the stand-in,
  not `serpapi.com`
- Everywhere: the archive endpoints in `search_metadata` are not served,
  `no_cache`, `async`, `output`, `json_restrictor`, and the 429 path

## Reference

- [Google Search API](https://serpapi.com/search-api)
- [Organic Results](https://serpapi.com/organic-results)
- [AI Overview Results](https://serpapi.com/ai-overview)
- [Google AI Overview API](https://serpapi.com/google-ai-overview-api)
- [Google Ads Transparency Center API](https://serpapi.com/google-ads-transparency-center-api)
- [Google Ads Transparency Center Ad Details API](https://serpapi.com/google-ads-transparency-center-ad-details-api)
- [Status and Error Codes](https://serpapi.com/search-api-status-and-error-codes)
