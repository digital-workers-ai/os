# Seeds — Mock Provider Server

> Faithful replicas of 29 third-party APIs on a single FastAPI process, backed by a shared ground-truth world.

---

## 1. Purpose

OS's connectors will pull from external APIs and dump raw payloads into `raw_event`. To develop and test the full pipeline (mapping, ER, enrichment, rules, goals, coaching) without real API credentials, `mock/` (mounted into its container as the `seeds` package) provides a mock server that replicates each provider's API contract — auth mechanism, pagination style, response schema, error format.

The mock server runs as a Docker Compose service (`mock`, project `os_v0`) alongside `postgres` and `backend`. It listens on `:8100` in the container, published to the host as `:8192`. Connectors reach it through a single env var, `MOCK_BASE_URL` (`http://mock:8100` in compose, `http://localhost:8192` from the host); each source appends its own path prefix, declared in `app/connectors/creds.py` — e.g. hubspot resolves to `{MOCK_BASE_URL}/hubspot`.

---

## 2. Architecture

Single FastAPI app, one `APIRouter` per provider module, path-prefixed so that every mock endpoint matches its production URL structure after the host swap:

```
mock:8100/hubspot/crm/v3/objects/contacts          → api.hubapi.com/crm/v3/objects/contacts
mock:8100/stripe/v1/customers                      → api.stripe.com/v1/customers
mock:8100/meta/v25.0/act_{id}/campaigns            → graph.facebook.com/v25.0/act_{id}/campaigns
mock:8100/salesforce/services/data/v67.0/query      → {instance}.salesforce.com/services/data/v67.0/query
```

All 27 provider modules share a single ground-truth dataset (`world.py`) and a shared library of auth decorators and pagination helpers (`helpers.py`). Each module renders the same underlying entities in its provider-specific response format.

---

## 3. File Structure

```
mock/
├── ARCHITECTURE.md              # This document
├── Dockerfile                   # python:3.12-slim, serves on :8100 as seeds.server
├── server.py                    # FastAPI app, mounts all routers, uvicorn entry
├── world.py                     # Shared ground truth: companies, people, subscriptions, ...
├── helpers.py                   # Auth decorators, pagination helpers
├── requirements.txt             # fastapi, uvicorn
│
├── providers/                   # One module per provider (or provider group)
│   ├── __init__.py
│   ├── hubspot.py               # CRM v3: contacts, companies, deals, OAuth
│   ├── stripe.py                # Customers, subscriptions, invoices, prices
│   ├── customerio.py            # Campaigns, activities, metrics, segments, newsletters
│   ├── meta.py                  # Meta Ads + FB Organic + IG Organic (shared Graph API)
│   ├── google_ads.py            # searchStream (POST, GAQL)
│   ├── google_analytics.py      # GA4 runReport (POST, offset pagination in body)
│   ├── google_sheets.py         # Sheets values.get
│   ├── calendly.py              # Scheduled events + invitees + event types
│   ├── smartlook.py             # Events, sessions, visitors
│   ├── salesforce.py            # SOQL query, sobjects, limits
│   ├── linkedin.py              # Ad accounts, campaigns, analytics, creatives
│   ├── pinterest.py             # Ad accounts, campaigns, ad groups, ads, analytics
│   ├── snapchat.py              # Organizations, accounts, campaigns, ad squads, ads
│   ├── twitter.py               # Accounts, campaigns, line items, analytics
│   ├── mailchimp.py             # Lists, members, campaigns, reports
│   ├── klaviyo.py               # Profiles, campaigns, flows, metrics (JSON:API)
│   ├── activecampaign.py        # Contacts, deals, automations, accounts
│   ├── sendgrid.py              # Contacts, singlesends, lists, stats
│   ├── twilio.py                # Messages, calls, accounts
│   ├── shopify.py               # Orders, customers, products
│   ├── woocommerce.py           # Orders, customers, products
│   ├── mixpanel.py              # Export (NDJSON), engage, insights
│   ├── amplitude.py             # Export (NDJSON), cohorts, usersearch
│   ├── segment.py               # Sources, destinations, profiles, tracking plans
│   ├── intercom.py              # Contacts, conversations, companies, notes
│   ├── zendesk.py               # Tickets, users, organizations, search
│   └── zoom.py                  # Meetings, recordings, VTT transcripts (no numbered doc)
│
└── docs/                        # API contracts (the source of truth)
    ├── 01-hubspot.md
    ├── 02-stripe.md
    ├── ...
    └── 28-zendesk.md
```

---

## 4. Ground Truth — `world.py`

All providers render the same canonical dataset. The entities are defined as Python dataclasses and imported by each provider module.

### 4.1 Entity Counts

| Entity | Count | Description |
|--------|-------|-------------|
| Companies | 10 | SaaS customers with deliberate business scenarios |
| People | 22 | Contacts distributed across companies |
| Subscriptions | 10 | One per company, various statuses and plans |
| Email campaigns | 8 | Mix of sent, scheduled, and draft |
| Ad campaigns | 12 | Across Meta, Google, LinkedIn, Pinterest, Snapchat |
| Support tickets | 10 | Clustered to create churn and billing signals |
| Analytics events | 16 | Product usage events for Mixpanel/Amplitude/Segment |
| Sales calls | 6 | Zoom transcripts with expected labels for enrichment |

### 4.2 Company Scenarios

Each company is designed to produce a specific signal when the full pipeline processes it:

| Company | Domain | Scenario |
|---------|--------|----------|
| Acme Corp | acme.io | **ER test** — "Acme Corp" in HubSpot, "ACME Corporation" in Stripe, "acme.io" in Customer.io, "Acme Corp." in Salesforce |
| Globex Inc | globex.com | **Healthy** — active subscription, $2,400/mo MRR, good ad spend ROI, feature suggestions only |
| Initech LLC | initech.io | **Churn risk** — 4 open tickets, old analytics events, declining engagement, paused ads |
| Umbrella Systems | umbrella.dev | **Churned** — canceled subscription, single contact, no recent activity |
| Wayne Enterprises | wayne.co | **New customer** — trialing since July 2026, onboarding events, getting-started ticket |
| Hooli Technologies | hooli.com | **High MRR** — $8,000/mo enterprise plan, heavy ad spender across 3 platforms |
| Pied Piper | piedpiper.com | **ER test** — Richard Hendricks has different emails across HubSpot, Stripe, Salesforce |
| Stark Industries | stark.io | **Past due** — payment failing, billing-related tickets |
| Cyberdyne Systems | cyberdyne.ai | **Missing fields** — no industry, no employee count, tests null handling |
| Soylent Corp | soylent.co | **ER test** — "Bob Smith" in HubSpot, "Robert Smith" in Stripe |

### 4.3 ER Variation Dicts

Three dictionaries map `(source, entity_id)` to the name/email as it appears in that source:

- `ER_COMPANY_NAMES` — company name variations (e.g., "Acme Corp" vs "ACME Corporation")
- `ER_PERSON_NAMES` — first/last name variations (e.g., "Bob" vs "Robert")
- `ER_PERSON_EMAILS` — same person, different email addresses across sources

Providers use these to introduce deliberate mismatches. When the ER pipeline runs against mock data, it must resolve "Acme Corp" (HubSpot) and "ACME Corporation" (Stripe) as the same entity.

---

## 5. Auth & Pagination — `helpers.py`

### 5.1 Auth Decorators

All auth is permissive — any non-empty credential in the correct format passes. The mock validates mechanism, not value.

| Decorator | Pattern | Used by |
|-----------|---------|---------|
| `require_bearer` | `Authorization: Bearer <token>` | HubSpot, Customer.io, Calendly, GA4, Sheets, Smartlook, LinkedIn, Pinterest, Snapchat, SendGrid, Segment, Intercom, Zendesk, Zoom |
| `require_basic_auth` | `Authorization: Basic <base64>` | Stripe, Twilio, WooCommerce, Mixpanel, Amplitude, Zendesk |
| `require_query_token` | `?access_token=<token>` | Meta (Graph API) |
| `require_header` | Custom header check | Klaviyo (`Authorization: Klaviyo-API-Key`), ActiveCampaign (`Api-Token`), Shopify (`X-Shopify-Access-Token`), Google Ads (`developer-token`), LinkedIn (`Linkedin-Version`, `X-Restli-Protocol-Version`), Intercom (`Intercom-Version`) |

### 5.2 Pagination Helpers

Seven pagination patterns cover every provider:

| Helper | Style | Returns | Used by |
|--------|-------|---------|---------|
| `cursor_paginate` | Cursor-based (`after` param) | `(page, next_cursor)` | HubSpot, Stripe, Customer.io, Meta, Smartlook, Zendesk |
| `offset_paginate` | Offset + limit | `(page, total)` | Mailchimp, ActiveCampaign |
| `token_paginate` | Opaque page token (base64 offset) | `(page, next_token)` | SendGrid, Calendly, Klaviyo, LinkedIn, Segment |
| `bookmark_paginate` | Bookmark string (base64 offset) | `(page, next_bookmark)` | Pinterest |
| `page_paginate` | Page number + page size | `(page, total)` | Twilio, WooCommerce |
| `session_paginate` | Session ID + page number | `(page, session_id, total)` | Mixpanel engage |
| `link_header_paginate` | `Link` header with `rel="next"` | `(page, link_headers)` | Shopify |

Notable outliers that don't use helpers: Google Ads (single-batch streaming response), GA4 (offset in POST body), Amplitude (full NDJSON dump, no pagination).

---

## 6. Provider Routing — `server.py`

The server mounts each provider's router with a prefix that absorbs the API version and path structure, so the route definitions inside each provider module stay clean:

| # | Provider | Mount Prefix | Auth | Doc |
|---|----------|-------------|------|-----|
| 1 | HubSpot | `/hubspot` | Bearer | `01-hubspot.md` |
| 2 | Stripe | `/stripe` | Basic Auth | `02-stripe.md` |
| 3 | Customer.io | `/customerio` | Bearer | `03-customerio.md` |
| 4-6 | Meta Ads + FB + IG | `/meta` | Query param | `04`, `05`, `06` |
| 7 | Google Ads | `/google-ads` | Bearer + `developer-token` | `07-google-ads.md` |
| 8 | GA4 | `/ga4/v1beta` | Bearer | `08-google-analytics.md` |
| 9 | Google Sheets | `/sheets/v4` | Bearer | `09-google-sheets.md` |
| 10 | Calendly | `/calendly` | Bearer | `10-calendly.md` |
| 11 | Smartlook | `/smartlook` | Bearer | `11-smartlook.md` |
| 12 | Salesforce | `/salesforce/services/data/v67.0` | Bearer | `12-salesforce.md` |
| 13 | LinkedIn | `/linkedin/rest` | Bearer + `Linkedin-Version` | `13-linkedin-ads.md` |
| 14 | Pinterest | `/pinterest/v5` | Bearer | `14-pinterest-ads.md` |
| 15 | Snapchat | `/snapchat` | Bearer | `15-snapchat-ads.md` |
| 16 | Twitter/X | `/twitter` | Bearer | `16-twitter-ads.md` |
| 17 | Mailchimp | `/mailchimp` | Bearer or Basic Auth | `17-mailchimp.md` |
| 18 | Klaviyo | `/klaviyo` | `Klaviyo-API-Key` header | `18-klaviyo.md` |
| 19 | ActiveCampaign | `/activecampaign` | `Api-Token` header | `19-activecampaign.md` |
| 20 | SendGrid | `/sendgrid` | Bearer | `20-sendgrid.md` |
| 21 | Twilio | `/twilio` | Basic Auth | `21-twilio.md` |
| 22 | Shopify | `/shopify` | `X-Shopify-Access-Token` | `22-shopify.md` |
| 23 | WooCommerce | `/woocommerce/wc/v3` | Basic Auth | `23-woocommerce.md` |
| 24 | Mixpanel | `/mixpanel` | Basic Auth | `24-mixpanel.md` |
| 25 | Amplitude | `/amplitude` | Basic Auth | `25-amplitude.md` |
| 26 | Segment | `/segment` | Bearer | `26-segment.md` |
| 27 | Intercom | `/intercom` | Bearer + `Intercom-Version` | `27-intercom.md` |
| 28 | Zendesk | `/zendesk/api/v2` | Bearer or Basic Auth | `28-zendesk.md` |
| 29 | Zoom | `/zoom` | Bearer | — |

28 numbered contracts plus Zoom, 27 modules — Meta Ads, FB Organic, and IG Organic share one module (`meta.py`) because they share the Graph API. Route conflicts (e.g., `/{id}/insights` matching ads, pages, and IG accounts) are resolved by dispatching on ID prefix (`act_`, `page_`, `ig_`).

---

## 7. Contract Docs — `docs/`

Each `docs/NN-provider.md` file is the source of truth for that provider's API contract. Provider implementations must match these docs exactly. Each doc covers:

- **Base URLs** — production and mock
- **Authentication** — mechanism, headers, error response format
- **Endpoints** — method, path, query/body params, full response schema with example JSON
- **Pagination** — style, params, termination condition
- **Error formats** — status codes and response shapes for auth failures, not-found, rate limits

The docs are research artifacts — they capture the real provider's API behavior as verified against production documentation. They are not generated from the mock code; the mock code is generated from them.

---

## 8. Running

```bash
docker compose -f app/docker-compose.yml up -d --wait mock
# → Uvicorn running on :8100 inside the container

curl http://localhost:8192/health
# → {"status": "ok", "providers": ["/hubspot", "/stripe", ...]}
```

In Docker Compose, the mock server runs as the `mock` service — reachable at `http://mock:8100` from other containers, and at `http://localhost:8192` from the host.

---

## 9. Design Decisions

- **Shared world, per-provider rendering.** A single `world.py` defines canonical entities. Each provider module transforms them into its own response format. This guarantees cross-source consistency — the same company appears in HubSpot, Stripe, and Salesforce with the same underlying data, just different field names and response shapes.
- **Deliberate ER variations.** Name, email, and company name variations are explicit in `ER_COMPANY_NAMES`, `ER_PERSON_NAMES`, and `ER_PERSON_EMAILS` dicts. The ER pipeline must reconcile these — they're not bugs, they're test fixtures.
- **Permissive auth, strict mechanism.** The mock doesn't validate credential values — any non-empty token passes. But it enforces the correct auth mechanism (Bearer vs Basic vs header vs query param) and required companion headers (e.g., `developer-token` for Google Ads). This catches connector misconfiguration without requiring real credentials.
- **One module per provider, not per endpoint.** Each provider file contains all endpoints for that provider. At ~60-370 lines per module, this keeps each provider self-contained without needing sub-packages.
- **Mount prefix absorbs API versioning.** Version paths like `/v1beta` (GA4) or `/services/data/v67.0` (Salesforce) live in the server.py mount prefix, not in route decorators. Provider modules define routes relative to their API root.
- **Contract docs are authoritative.** The `docs/` files are research artifacts that capture real API behavior. Mock implementations are verified against them, not the other way around.
