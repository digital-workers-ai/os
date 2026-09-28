# Configuration

[DW-OS](../README.md) › Configuration

Everything is read from the environment, with `app/.env` loaded first (`app/backend/app/config.py`). Every setting has a default, so an empty file runs, with every source on its stand-in and every model layer off. API keys have no defaults, and a layer switched on without its key stops the backend from starting.

```bash
cp app/.env.example app/.env
```

## Contents

- [Core](#core)
- [Connectors and entity resolution](#connectors-and-entity-resolution)
- [Model layers](#model-layers)
- [Search](#search)
- [Studio](#studio)
- [API keys](#api-keys)
- [Source credentials](#source-credentials)
- [Compose and front-end variables](#compose-and-front-end-variables)
- [GitHub agents](#github-agents)
- [Ports](#ports)

## Core

| Variable | Default | What it does |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://os:os@localhost:5442/os` | Postgres connection; compose points it at the `postgres` service |
| `MOCK_BASE_URL` | `http://localhost:8192` | Where the stand-in providers answer |
| `SYNC_RUN_RETENTION_DAYS` | `30` | Sync runs older than this are pruned |
| `ENGINE_RUN_RETENTION` | `200` | Rebuild receipts kept |
| `CLOCK_PINNED_AT` | unset | Fixes the app's clock at one instant; must carry a timezone, such as `2026-09-04T12:00:00Z` |

## Connectors and entity resolution

| Variable | Default | What it does |
|---|---|---|
| `STAND_INS_ONLY` | `false` | Every source answers from its stand-in, whatever keys are set |
| `CONNECTOR_MAX_PAGES` | `500` | Pages one paginated request chain may read before it stops and says so |
| `CONNECTOR_MAX_BYTES` | `52428800` | Bytes one paginated request chain, or one export, may read |
| `ER_BUCKET_CAP` | `50` | Records sharing one identity value before the bucket is quarantined instead of merged |
| `ER_ONE_RECORD_PER_SOURCE` | `true` | A canonical entity holds at most one record per tool |

## Model layers

Each layer is off until its switch is `true` and its key is set. See [Agents](agents.md).

| Variable | Default | What it does |
|---|---|---|
| `ENRICHMENT_ENABLED` | `false` | Labeled facts from text |
| `ENRICHMENT_MODEL` | `claude-sonnet-5` | Model for enrichment |
| `ENRICHMENT_MAX_TOKENS` | `8000` | Output cap per enrichment call |
| `ENRICHMENT_MAX_CALLS_PER_RUN` | `200` | Model calls per enrichment run, across all readings |
| `ENRICHMENT_CONCURRENCY` | `4` | Enrichment calls in flight at once |
| `COACHING_ENABLED` | `false` | Role briefings |
| `COACHING_MODEL` | `claude-sonnet-5` | Model for briefings |
| `COACHING_MAX_TOKENS` | `8000` | Output cap per briefing |
| `CONVERSATION_ENABLED` | `false` | The ask agent |
| `CONVERSATION_MODEL` | `claude-sonnet-5` | Model for the ask agent |
| `CONVERSATION_MAX_TOKENS` | `8000` | Output cap per model call |
| `CONVERSATION_MAX_TURNS` | `8` | Model calls per question |
| `CONVERSATION_MAX_TOOL_RESULT_CHARS` | `16000` | A tool result is cut beyond this, with a note asking for a narrower question |
| `CONVERSATION_MAX_HISTORY_TURNS` | `12` | Earlier exchanges loaded from the thread; the last 12 messages are replayed |
| `CONVERSATION_MAX_TURN_CHARS` | `4000` | Each replayed message and the new question are cut beyond this; stored turns are kept whole |

## Search

Word search is always on. Meaning search and reranking are opt-in.

| Variable | Default | What it does |
|---|---|---|
| `EMBEDDINGS_ENABLED` | `false` | Meaning search over transcript chunks; embeddings refresh after each rebuild |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model |
| `EMBEDDING_DIMS` | `1536` | Vector width; must match the database column, so changing it needs a migration |
| `EMBEDDING_BATCH` | `100` | Chunks per embedding request |
| `EMBEDDINGS_MAX_CALLS_PER_RUN` | `200` | Embedding requests per run |
| `SEARCH_CHUNK_CHARS` | `1200` | Target size of a transcript chunk |
| `RERANK_ENABLED` | `false` | Rerank the top results of combined word and meaning search; needs `EMBEDDINGS_ENABLED` to have any effect |
| `RERANK_MODEL` | `zerank-2` | Reranker model |
| `RERANK_TOP` | `20` | Results sent to the reranker |

## Studio

See [Studio](studio.md).

| Variable | Default | What it does |
|---|---|---|
| `STUDIO_ENABLED` | `false` | Skill runs; needs `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` |
| `STUDIO_MODEL` | `claude-opus-5` | Model that routes requests and runs a content skill |
| `STUDIO_MAX_TOKENS` | `8000` | Output cap per skill turn |
| `STUDIO_MAX_TURNS` | `16` | Tool-call rounds per skill run |
| `PAINT_MODEL` | `gpt-image-2` | OpenAI image model that paints pictures |
| `MEDIA_DIR` | `/media` | Where asset files are written; compose mounts a volume there |
| `RENDER_URL` | `http://localhost:8200` | Where the renderer answers; compose points it at the `render` service |
| `MARKETER_DAILY` | `false` | Fill the calendar's empty slots every day |
| `MARKETER_HOUR` | `6` | UTC hour the daily fill runs |

## API keys

| Key | Needed by | Also |
|---|---|---|
| `ANTHROPIC_API_KEY` | Enrichment, briefings, the ask agent, the studio | Sends the Claude Spy source to the real API |
| `OPENAI_API_KEY` | Meaning search, the studio's pictures | |
| `ZEROENTROPY_API_KEY` | Reranking | |

## Source credentials

A source reads its real API once every variable it names is set, and its stand-in when none is. A partial set fails that source's sync and names what is missing. `<SOURCE>_BASE_URL` overrides the host for a source on its real API. `app/.env.example` lists every variable, blank. See [Connectors](connectors.md#real-api-or-stand-in).

| Source | Variables |
|---|---|
| ActiveCampaign | `ACTIVECAMPAIGN_BASE_URL`, `ACTIVECAMPAIGN_API_KEY` |
| Amplitude | `AMPLITUDE_API_KEY`, `AMPLITUDE_SECRET_KEY` |
| Calendly | `CALENDLY_ACCESS_TOKEN`, `CALENDLY_USER_URI` |
| ChatGPT, Perplexity, Gemini | `OPENROUTER_API_KEY` |
| Claude | `ANTHROPIC_API_KEY` |
| Google Ads Transparency | `SERPAPI_API_KEY`, `OPENROUTER_API_KEY` |
| Google Search | `SERPAPI_API_KEY` |
| HubSpot | `HUBSPOT_ACCESS_TOKEN` |
| Intercom | `INTERCOM_ACCESS_TOKEN` |
| Klaviyo | `KLAVIYO_API_KEY` |
| LinkedIn Ad Library, TikTok Ads Library, Meta Ad Library | `SEARCHAPI_API_KEY` |
| LinkedIn Company Posts, X Posts, Instagram Posts, TikTok Posts | `BRIGHTDATA_API_KEY` |
| Mailchimp | `MAILCHIMP_API_KEY` |
| Mixpanel | `MIXPANEL_SERVICE_ACCOUNT_USERNAME`, `MIXPANEL_SERVICE_ACCOUNT_SECRET`, `MIXPANEL_PROJECT_ID` |
| Shopify | `SHOPIFY_STORE_DOMAIN`, `SHOPIFY_ACCESS_TOKEN` |
| Stripe | `STRIPE_API_KEY` |
| Twilio | `TWILIO_ACCOUNT_SID`, `TWILIO_API_KEY_SID`, `TWILIO_API_KEY_SECRET` |
| X (Twitter) | `TWITTER_BEARER_TOKEN`, `TWITTER_USER_ID` |

Salesforce, Zoom, WooCommerce, Zendesk, Customer.io, SendGrid, Google Ads, Meta Ads, LinkedIn Ads, Pinterest, Snapchat, Google Analytics, Segment, Smartlook and Google Sheets have no real-API path in this repository yet.

## Compose and front-end variables

These are read by compose and the Vite servers, not by the backend.

| Variable | Default | Read by | What it does |
|---|---|---|---|
| `BACKEND_URL` | `http://localhost:8092` | console, dashboard, Spy, studio | Where each app's `/api` proxy (and the console's `/mcp` proxy) sends requests; compose sets `http://backend:8000` |
| `VITE_CONSOLE_URL` | `http://localhost:3092` | dashboard, Spy | Where "Open in Console" links point; set it when the console is not on localhost |

## GitHub agents

These are GitHub Actions repository variables and secrets, read by `.github/workflows/operator.yml`, `operator-build.yml` and `taste.yml`, not app settings. See [Agents → Setting up the GitHub agents](agents.md#setting-up-the-github-agents).

| Name | Kind | What it does |
|---|---|---|
| `OPERATOR_ENABLED` | variable | `true` switches on the operator and its builder; anything else and every run is skipped |
| `STUDIO_AGENTS_ENABLED` | variable | `true` switches on the taste agent |
| `OPERATOR_SNAPSHOT_S3` | variable | `bucket/path/to/os.dump`, a `pg_dump` custom-format file on S3 |
| `OPERATOR_AWS_ROLE_ARN` | variable | Role assumed through OIDC to read it; the region is `us-east-1` |
| `OPERATOR_SNAPSHOT_GCS` | variable | `bucket/path/to/os.dump` on Cloud Storage |
| `OPERATOR_GCP_WORKLOAD_IDENTITY_PROVIDER` | variable | Workload identity provider the runner authenticates through |
| `OPERATOR_GCP_SERVICE_ACCOUNT` | variable | Service account it impersonates to read the dump |
| `ANTHROPIC_API_KEY` | secret | The agents' model |
| `OPERATOR_GITHUB_PAT` | secret | Token the operator uses for issues and the builder and taste agent for pull requests |

Set the S3 pair or the GCS pair, never both; the run refuses two sources. With neither, the operator syncs the stand-ins and audits that, and the taste agent finds an empty database. Only the variable gates a run: with it on and a secret missing, runs start and fail.

The approval gate checks that whoever applies `approved` or replies LGTM is a repository admin. Give `OPERATOR_GITHUB_PAT` to an account that is not an admin, so an agent acting with it cannot pass that gate or push past branch protection.

## Ports

| Service | Port |
|---|---|
| Console | 3092 |
| Dashboard | 3093 |
| Spy | 3094 |
| Studio | 3095 |
| Backend (API and `/mcp`) | 8092 |
| Stand-in providers | 8192 |
| Postgres | 5442 |
| Renderer | internal only (8200) |

Compose publishes these on every interface. There is no authentication in front of any of them, so run the stack on localhost or behind your own network boundary (see `SECURITY.md`).
