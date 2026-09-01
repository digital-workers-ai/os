# OS v0

An AI Operating System substrate: it pulls raw data from the tools a company uses, projects it into a clean entity graph, and (in later slices) computes metrics, rules, and goals on top. Deterministic by design — same inputs, same outputs, no model calls in the pipeline.

## Concepts

**Source** — one external tool (HubSpot, Stripe, …). Each has a connector that knows how to pull its API. In development every source is served by the vendored mock estate in `mock/`, 27 providers rendering one shared fictional world.

**Raw event** — one payload exactly as a source returned it, stored append-only in `raw_event`. Nothing is ever edited or deleted here; a record that changes gets a new row. This is the system's ground truth: everything else can be rebuilt from it.

Think of `raw_event` as the enrollment book: every record ever seen is in it, permanently.

**Sync** — one pull attempt for a source (`POST /api/sync`). It records itself in `sync_run` — including refusals, id collisions, and truncations — because a quiet source and a broken one must never look the same.

**Entity** — one thing a single source knows about: a company, a person, a deal. Identity is structural — `(source, entity_type, source_id)` — so the same real-world company known to two tools is, at this layer, two entities.

**Canonical entity** — one real-world thing, merged across tools. Resolution buckets entities on declared identity attributes (a company's domain, a person's email) and records the evidence on every membership (`domain=acme.io`). Survivorship then folds the members' facts into one value per attribute — newest observation wins, declared source priority breaks ties — keeping receipts (winning source, raw event, disagreement count). Blocklists stop false merges: a free-mail domain identifies no company, a placeholder identifies nothing.

**Survivorship** — how many opinions become one answer. When a cluster's members disagree about an attribute (HubSpot: "Acme Corp", Stripe: "ACME Corporation"), the fold picks one value per attribute by a fixed rule: newest observation wins (on the provider's clock), a time tie falls to declared `source_priority`, and a remaining tie falls to stable name order — so a rebuild always picks the same winner. Along the way it counts disagreements (distinct losing values, stamped on the fact), lets a winning clear silence the attribute entirely (an empty field that is *fresher* beats an old value), and stamps receipts on every winner: which source, which raw event, observed when.

**Fact** — one attribute of one entity as asserted by one source: "hubspot says company hs_company_001's domain is acme.io." Each fact keeps its provenance (which raw event asserted it, when the provider observed it). Facts obey the **three-state rule**:
- *absent* — the source never mentioned the attribute: no fact row at all
- *cleared* — the source said "this is empty": a fact row with `is_null` true
- *value* — a normalized value that survived its transform

A value the transform refused (garbage date, non-numeric amount) becomes none of these — it is counted and named in the report, never stored and never turned into a null.

**Observation time** — every fact carries `observed_at`: when the data changed *according to the provider's own clock* (each connector's `OBSERVED_AT` declares where that timestamp lives in the payload). It exists because "newest observation wins" only works on the provider's clock — on our ingestion clock, whichever source synced last would win every disagreement. When the provider's timestamp is missing or unreadable, ingestion time is used and the substitution is counted in the report, never silent.

**seq, first_seq, minted_seq** — one currency at three levels. `seq` is the raw-event insertion counter, the estate's unambiguous "which came first" (timestamps can't order rows written in one transaction). `first_seq` is a record's earliest seq — when it was *first* seen; edits add higher seqs, so it never moves. `minted_seq` is the founding record's `first_seq` on a canonical entity. Resolution processes records in `first_seq` order and mints the canonical id from the earliest record's key — so editing a record can never re-anchor a cluster or change its id.

**ProjectedEntity / ProjectedFact** — the rebuild's in-memory intermediates, produced by the pipeline before anything is written. A `ProjectedFact` is one normalized value plus everything needed downstream: the numeric form for number attributes, the asserting raw event, the observation time and whose clock it came from, and the seq. A `ProjectedEntity` groups those facts under one `(source, entity_type, source_id)` with its `first_seq` and the `anchor_key` string its database id is hashed from. Resolution, survivorship, and links all operate on these objects; only at the end does the rebuild translate them into `entity` / `entity_fact` rows. They never leave the process — if you're reading the database or the API, you're seeing their persisted results, not them.

**Knowledge files** — the YAML files at the repo root that make the system declarative:
- `ontology.yaml` — what entities exist and what typed attributes each may have. An entity's `identity:` list names which attributes count as merge evidence — `company: [domain]`, `person: [email]`: two records sharing a normalized identity value become one canonical entity. The list is deliberately short: names are never identity (too fuzzy — "Acme Corp" vs "ACME Corporation" is the problem, not the key), vendor ids never (each source's ids are its own), and an entity with no `identity:` list (subscription) is never merged at all — one tool owns it. `source_priority:` orders sources for survivorship tiebreaks; `relationships:` declares the edges links may build and what grounds them.
- `mappings.yaml` — one line per raw field worth keeping: `source.object_type.path → attribute`
- `transforms.yaml` — which normalizer each attribute's values pass through
- `synonyms.yaml` — which provider spellings fold to one canonical status
- `metrics.yaml` — the numbers the estate answers with, as declared aggregates

Adding a field or a metric to the system is editing a YAML line, not writing code.

**Metric** — a number computed over the canonical layer, declared in `metrics.yaml` (a knowledge file like the rest: `mrr` is `SUM(mrr)` over subscriptions where `status: active`). Because metrics run over canonical entities, `COUNT(company)` counts Acme once — not once per tool. Every value carries receipts: the population before the filter, how many rows actually fed the aggregate, who lacked the attribute, and the raw provider fields the number walked in from (`mrr` traces to `stripe.subscriptions._amount_monthly`). The semantics refuse to flatter: a sum of nothing is 0 but an average of nothing is unknown (`None`) — a zero average would read as a measurement that never happened; mixed currencies refuse to aggregate rather than silently sum; and one broken definition errors on its own row without taking the catalog down. Served by `GET /api/metrics`.

**Snapshot** — one metric's value written down with a timestamp: a diary entry for a number. Live values (`GET /api/metrics`) are always *now* and forget; `POST /api/metrics/snapshots` records every metric as a row, and repeated scheduled calls accumulate the series `GET /api/metrics/history` serves — what charts draw and trend goals judge. Three rules, each from a real bug: only the snapshot route writes history (never a rebuild or a page load — v4's read-triggered snapshots turned history into a graph of how often the dashboard was open); a run that measured nothing stores NULL, not zero, with the row still written ("couldn't measure" and "measured zero" are different claims, and "nothing measured" differs from "nobody ran the job"); a broken metric costs one row, never the snapshot.

**Transform** — a pure normalizing function (`normalize_domain`, `normalize_money`, …). Transforms refuse rather than guess: a value they can't interpret raises a named reason (`not_a_date`, `not_a_number`) that lands in the report. A closed registry — data never selects arbitrary code.

**Rebuild** (projection) — `POST /api/rebuild`: wipe the entity layer and recompute it from the newest raw event per record, through mappings and transforms. Deterministic (ids are content-derived uuid5s — two rebuilds produce byte-identical rows), locked (a concurrent rebuild gets a 409), and rebuildable at any time because raw events are never lost.

**Report** — the rebuild's self-accounting (`GET /api/report`): every refused value bucketed by reason, every cleared field, every mapping line that matched nothing (`dead_paths` — how you notice a provider renamed a field), every failed row. The design rule: nothing is dropped silently.

## Running

```
./test.sh unit    # ruff + full suite, 100% line+branch coverage enforced
./test.sh e2e     # against the live mock estate
./format.sh       # apply lint fixes and formatting
```

The stack is Docker Compose (`app/docker-compose.yml`): postgres :5442, mock :8192, backend :8092. `test.sh` starts it as needed.

## Layout

- `ROADMAP.md` — the feature-slice plan to v11 parity, checkbox-tracked
- `mappings.yaml`, `ontology.yaml`, `transforms.yaml`, `synonyms.yaml`, `metrics.yaml` — the knowledge files
- `app/backend/` — FastAPI backend; tests in `app/backend/tests/`
- `app/backend/app/sources/` — one package per source: connector plus extract hook
- `mock/` — vendored mock providers (verbatim; exempt from repo style rules)
