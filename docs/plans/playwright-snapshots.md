# Feature: Playwright snapshot tests for the console

## Summary
Every page of the console gets a visual baseline, captured by Playwright in the Linux Playwright image through docker compose, against a deterministic estate: mocks synced, rebuilt twice, and a repo-owned seed that adds enrichment facts, briefings and pins every timestamp to a fixed clock. Actions that cannot run deterministically (Generate, Sync, failures) are mocked at the browser with route interception. One viewport, 1280×800, chromium only.

## Changes

### Infrastructure
- [x] Add `@playwright/test` and `snap` / `snap:update` scripts — `app/frontend/package.json`
- [x] Playwright config: `e2e/` dir, 1280×800, reduced motion, fixed clock, no platform suffix in baseline names — `app/frontend/playwright.config.ts`
- [x] Fixtures: extended `test`, `settle`, `snap`, `openSelect`, `mockJson`, `NOW` — `app/frontend/e2e/fixtures.ts`
- [x] Self-host Space Grotesk and Science Gothic, drop the Google Fonts link — `app/frontend/public/fonts/`, `app/frontend/src/styles.css`, `app/frontend/index.html`
- [x] `playwright` compose service on `mcr.microsoft.com/playwright`, profile `snap` — `app/docker-compose.yml`
- [x] `test.sh snap` and `test.sh snap-update`: sync, rebuild twice, seed, run — `test.sh`
- [x] CI job `snapshots` with diff artifacts on failure — `.github/workflows/ci.yml`
- [x] Ignore `e2e/results` and `e2e/report` — `.gitignore`

### Seed
- [x] Deterministic demo data anchored at `2026-09-04T12:00:00Z`: facts, runs, briefings — `app/backend/tools/seed_demo.py`
- [x] Shift sync, rebuild, observation and ingestion timestamps to fixed offsets from the anchor, order preserved — same file

### Specs (one file per page)
- [x] Global chrome and intro — `app/frontend/e2e/chrome.spec.ts`
- [x] Home — `app/frontend/e2e/home.spec.ts`
- [x] Activity — `app/frontend/e2e/activity.spec.ts`
- [x] Metrics — `app/frontend/e2e/metrics.spec.ts`
- [x] Entities: Canonical, Raw entities, Visualize — `app/frontend/e2e/entities.spec.ts`
- [x] AI: gated and live, Enrichment, Coaching — `app/frontend/e2e/ai.spec.ts`
- [x] Definitions: seven tabs — `app/frontend/e2e/definitions.spec.ts`
- [x] Config: Sources, Rebuild — `app/frontend/e2e/config.spec.ts`
- [x] Baselines — `app/frontend/e2e/__screenshots__/`

## Notes
- The AI page's disabled state is the shipped default; the live state is captured by mocking the two index endpoints' `enabled` flag.
- Generate, Sync all, per-source Sync, Rebuild and failure banners are captured through mocked responses, so the suite never calls a model and never mutates the estate.
- The Enabled toggle on Sources is exercised for real and restored at the end of the spec.
- Baselines must only ever be generated inside the compose service; a macOS run produces different text rasterisation.
