# Roadmap: v11 parity, one PR at a time

Sizes are v11 production LOC; tests add ~1.5–2x. Source paths are v11's (`../v11/app/backend/`). Every PR folds in the relevant fixes from v11's `TODO.md` (defect areas A–J) instead of replicating them.

- [ ] 1. feat: repo bootstrap — coverage-gated test.sh, ruff gate, health route (open: #1)
- [ ] 2. feat: schema + config — `models.py`, `config.py`, `db.py`, `caches.py` (~730)
- [ ] 3. feat: raw store + sync report — `store.py`, `engine/report.py` (~220)
- [ ] 4. feat: transforms registry — `engine/transforms.py`, mutmut config (~395)
- [ ] 5. feat: strategies + paginators — `engine/strategies.py`, `connectors/paginators.py` (~553)
- [ ] 6. feat: ontology — `knowledge/ontology.yaml`, `engine/ontology.py`, checks seed (~430)
- [ ] 7. feat: mappings — `mappings.yaml`, `transforms.yaml`, `engine/mappings.py` (~440)
- [ ] 8. feat: connector infra — `client.py`, `util.py`, `creds.py`, `registry.py`, `catalog.py`, 2 connectors (~600)
- [ ] 9. chore: vendor mock providers — verbatim v9 seeds copy, compose `mock` service (~5.3k vendored, spot-check review)
- [ ] 10. feat: connectors batch 1 — ~8 modules + fixture replays
- [ ] 11. feat: connectors batch 2 — ~8 modules + fixture replays
- [ ] 12. feat: connectors batch 3 — remaining modules + fixture replays
- [ ] 13. feat: sync orchestration — `sync.py`, `sources.yaml`, manifests, sources/raw APIs (~470)
- [ ] 14. feat: projection — `engine/pipeline.py`, first extract hooks (~500)
- [ ] 15. feat: remaining extract hooks (~300)
- [ ] 16. feat: entity resolution — `engine/resolver.py`, vendored adversarial corpus, precision test (~481; v11 baseline 0.92)
- [ ] 17. feat: survivorship + links — `engine/survivorship.py`, `engine/links.py` (~190)
- [ ] 18. feat: rebuild orchestrator — `engine/run.py`, entities API, first e2e, schemathesis (~600)
- [ ] 19. feat: metrics grammar + filters (~1/3 of `engine/metrics.py`)
- [ ] 20. feat: metrics evaluation + receipts
- [ ] 21. feat: metrics snapshots + history, metrics API, `metrics.yaml`
- [ ] 22. feat: rules — `engine/rules.py`, `rules.yaml`, insights API (~400)
- [ ] 23. feat: goals — `engine/goals.py`, `goals.yaml`, `checks.py` completed (~350)
- [ ] 24. feat: llm boundary — `app/llm/`, AST boundary test (~110)
- [ ] 25. feat: enrichment vocabulary — `enrichment.yaml`, `vocabulary.py` (~350)
- [ ] 26. feat: enrichment reader + store + API (~730)
- [ ] 27. feat: inferred metrics over `enriched_fact` (~150)
- [ ] 28. feat: coaching — `briefer.py`, prompts, coaching API (~350)
- [ ] 29. feat: ask — `conversation/store.py`, `agent.py`, conversation API (~530)
- [ ] 30. feat: knowledge API + final checks sweep (~300)

Couplings: extract hooks' free-mail list lands in a shared module (not resolver) so 15 need not wait for 16; vocabulary (25) precedes inferred metrics (27).
