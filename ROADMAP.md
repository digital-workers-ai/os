# Roadmap: v11 parity, one feature at a time

Every PR fulfills a feature: something runnable, stated as a demo criterion the reviewer can exercise. Code, tables, settings, and transforms land only with the slice that first consumes them. v11 (`../v11/`) is the reference implementation: each slice ports the relevant modules, tests, and `TODO.md` defect fixes (areas A–J), built in rather than replicated. Parity is confirmed at the end by porting the remaining v11 test inventory, not by per-file diffing along the way.

## Foundation (shipped, functionality-first)

- [x] 1. Repo bootstrap — coverage-gated test.sh, ruff gate, health route (#1)
- [x] 2. raw_event + config + db layer (#2)
- [x] 3. Raw store + sync report — B1 query, F2 store half (#3)

## Depth first: one source, end to end

- [x] 4. chore: the mock estate answers — vendor v9 seeds verbatim, compose `mock` service. Demo: `curl mock:8100/health` and a provider endpoint return data.
- [x] 5. feat: sync HubSpot — `POST /api/sync` pulls companies/contacts/deals into `raw_event`; `GET /api/raw` shows rows. Brings: client, creds, registry, hubspot connector, sync.py, `sync_run` table, raw/sources APIs. Fixes: F2 (handler half), J3, J4/F3, F1, H3. Deliberately absent: manifests/tombstones and any deletion detection (Carlos, 2026-08-31) — upstream deletions go undetected; if wanted later it is its own slice. Defect 1 and A1/A2/A4/A5/C1/A3 are moot without it.
- [x] 6. feat: raw becomes entities — `POST /api/rebuild` projects HubSpot into `entity`/`entity_fact`; `GET /api/entities` lists companies with facts. Brings: ontology/mappings/transforms subsets HubSpot needs, caches.py, pipeline, engine_run. Fixes: A3.
- [x] 7. feat: one company across tools — sync Stripe too; resolution merges on identity attrs with evidence; `GET /api/entities` shows one Acme with both sources' facts, folded. Brings: resolver, survivorship, canonical tables, aliases, stripe connector + extract hook (D1 currency placement, D3). Fixes: B1 (consumed), B2.
- [x] 8. feat: the first metric — MRR over the canonical layer with receipts; `GET /api/metrics` answers with the number and what produced it. Brings: metrics grammar subset, metrics.yaml first lines, metrics API.
- [x] 9. feat: metrics remember — `POST /api/metrics/snapshots` is the one history writer (deliberately not the rebuild: a series must count scheduled runs, not pipeline runs), `GET /api/metrics/history`. Brings: `metric_snapshot` table, history never pruned by design. Fixes: E1, E6 (E5 is inferred-only code — moved to 21).
- [x] 10. feat: rules surface attention — rule predicates over facts; `GET /api/insights/rules` names entities worth a look. Brings: rules.py, rules.yaml subset.
- [x] 11. feat: goals judge metrics — targets + strategies; `GET /api/insights/goals` says met/unmet with progress. Brings: strategies.py (at_least/at_most/increasing), goals.py, goals.yaml. Fixes: E2 (consumer half), E6 (consumer half), J13. Param strategies + check_goals + H4 wait for 16; E3 with the first negative metric filter.

## Widen: the estate

- [x] 12. feat: six more sources (batch 1: zendesk, intercom, klaviyo, calendly, sendgrid, customerio) — connectors + knowledge lines + fixture replays + the links match branch. Demo: sync-all lands rows for each; dead_paths empty; persons still 22 across eight tools.
- [x] 13. feat: six more sources (batch 2: salesforce, shopify, woocommerce, mailchimp, twilio, google_sheets) — basic auth, header pagination, offset pagination, the SOQL cursor chain. Fixes: D2 (sheets numbers refuse rather than strip), F3 (reported as collisions, not resolved). F1 already landed with slice 5's client.
- [x] 14. feat: six more sources (batch 3: meta, google_ads, google_analytics, activecampaign, zoom, segment) — POST + query-token + micros + transcripts; the multi-object merge returns with meta; zoom's VTT/UUID/NUL handling whole. Twenty sources syncing.
- [x] 15. feat: remaining sources (batch 4: amplitude, mixpanel, smartlook, snapchat, twitter, pinterest, linkedin) — all 27 syncing; `GET /api/sources` serves catalog + honest sync status (validation labels arrive with checks, slice 16).
- [x] 16. feat: the build refuses a broken estate — checks.py cross-validates all seven knowledge files at boot and before every rebuild; a bad file fails, named. Brings: validation labels on /api/sources DERIVED from mappings + fixtures/real (no sources.yaml — a hand-kept echo of derivable truth, removed in review), threshold_band + PARAMS + H4 guard, avg_deal_size goal. Deferred with their grammar: group_by/window/enrichment checks; streak waits for window metrics (unscheduled); exact/within_pct/decreasing/growth_rate wait for consumers; knowledge API waits (24 or later).
- [x] 17. feat: resolution survives an adversarial estate — vendor v8 corpus; precision test ≥ 0.92; guards (bucket cap, one-per-source, corroboration, quarantine) live. Brings: ER settings with consumers. Shipped with v11's stricter floors (company 0.99/0.88, person 0.98/0.92 pairwise; measured company 1.000, person 0.986); multi-hit folding + fold-aliases; identity_scope with external_ref promoted to tenant-scoped person identity; C2 fail-closed built in; C1 moot (no tombstones); C3 pinned as a measured tradeoff, not fixed.
- [x] 18. feat: no route 500s — schemathesis contract suite over the OpenAPI; NUL middleware (J10); offset caps (MAX_OFFSET). Caps had already landed with their routes; the new work was the middleware (both halves), the entity 404 joining the spec, and the e2e fuzz suite with its three write exclusions guarded by a test.

## Inference, behind the boundary

- [x] 19. feat: one door to the model — app/llm quarantine (by convention), validate_startup. Brings: enablement flags with their enforcement. Minimal by consumer: app/llm is the lazy client + LLMError alone (complete/parse/converse arrive with 22/20/23); only ENRICHMENT_ENABLED lands (coaching/conversation flags wait for their layers); boot order now ["config","schema","checks","serving"]. The AST boundary suite was built, then removed in review (Carlos): quarantine is a convention PR review upholds, not a proof the suite enforces.
- [x] 20. feat: a transcript becomes labeled facts — enrichment vocabulary + reader + store + API; coverage stated, not assumed. Fixes: G1, G2, G3. Shipped as one PR (Carlos's call at ~2.4k lines). llm.parse lands with its consumer (G2's three catches whole); live suite behind the llm marker, no --llm option (test.sh's -m filter already gates); no collection-gating tests; enrichment.yaml at repo root, checked by check_enrichment at boot.
- [ ] 21. feat: inferred metrics — metrics over `enriched_fact`, digest-stamped snapshots. Fixes: E4, E5.
- [ ] 22. feat: a role gets a briefing — coaching briefer + prompts + API, fenced estate data.
- [ ] 23. feat: ask the estate a question — conversation agent + tools + threads + API. Fixes: H2 (narrowable metrics tool).

## Parity

- [ ] 24. chore: parity audit — port every remaining v11 test, diff `def test_` inventory per module, close gaps or record deliberate divergences.

Slice contents above are starting points, not contracts: the study step decides each slice's exact scope by what the demo needs, and later slices absorb what earlier ones deferred.
