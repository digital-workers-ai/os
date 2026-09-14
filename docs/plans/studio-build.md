# Studio — one branch, one PR

Decided 2026-09-14: the twelve slices in `studio.md` collapse into a single pull request on `feat/studio`, built by parallel agents on disjoint files. `studio.md` keeps the slice list as the order of work; this file is the contract every agent builds against.

Slice 1 (competitor sources batch 1) is already committed: `7033ed2` red, `8ef39f4` mock, `b07675e` backend, `32e40b5` fixtures.

## What Studio is

The backend generates every marketing asset by running a skill. A skill is `.claude/skills/dw-<name>/SKILL.md`; the skill runner executes it as a bounded agent loop with a fixed toolbelt, in one of three modes — `draft` (cheap preview, no paid render), `build` (the real render, after a person approves), `chat` (called over MCP from Claude.ai or Claude Code). A marketer agent runs daily, fills the calendar's empty slots with drafts, and proposes counter-work when it notices something in the swipe file. A person approves in Studio; approval starts a build. A taste agent runs nightly, reads rejections, edits and feedback, and opens PRs against the skills.

Studio uses none of v12's metrics, goals, snapshots, rules, findings or briefings. It never posts or publishes, and measures nothing. Counts in the competitor views are plain queries over dated entities. Numbers inside an asset come only from `definitions/brand/proof.md`.

## Schema

Nine tables, all normalized, no JSON column holding structured data. One migration for the lot, generated once.

```
proposal              seq, kind, title, slot_date, slot_name, reactive, skill, skill_sha,
                      status(open|approved|rejected|built), reason, note, created_at, decided_at
proposal_evidence     id, proposal_seq, kind(brand|transcript|competitor_ad|asset), ref, detail
proposal_claim        id, proposal_seq, text, source_kind(proof|transcript|competitor_ad),
                      source_ref, verified
proposal_draft        id, proposal_seq, path, media_type, bytes        (the cheap preview files)
asset                 seq, name, kind, look, origin(proposal|chat), proposal_seq, ancestor_ref,
                      created_at
asset_file            id, asset_seq, version, path, media_type, bytes, note, created_at
skill_run             seq, skill, skill_sha, mode, caller(marketer|studio|mcp), proposal_seq,
                      asset_seq, stage, status(running|ok|failed), error, duration_ms,
                      cost_usd, started_at, finished_at
skill_run_tool_call   id, skill_run_seq, tool, ok, duration_ms, detail
agent_run             seq, agent(marketer|taste), trigger, read_detail, proposed, duration_ms,
                      cost_usd, ok, error, created_at
slot_skip             id, slot_date, slot_name, created_at
```

Files live under a media volume; a row holds the path and the bytes count, never the bytes.

## Definition files

| File | Holds |
|---|---|
| `definitions/competitors.yaml` | competitors, plus `keywords`, `prompts`, `engines` |
| `definitions/brand/*.md` | brand-brain, voice, audiences, objections, language, proof, pillars |
| `definitions/calendar.yaml` | slots: cadence, kind, look, theme source, reactive caps |
| `definitions/looks/<name>/` | scene vocabulary, limits, `base.html.j2`, sample `content.yaml` |
| `definitions/enrichment.yaml` | gains the `competitor_creative` reading |
| `definitions/ontology.yaml` | gains `ranking`, `ai_mention`, `competitor_page`, `competitor_post` |

Every new file is checked at boot by its own module under `app/backend/app/engine/`, wired into `checks.run`.

## Backend module layout

```
app/backend/app/
  engine/competitors.py     competitors.yaml loader + check        (exists)
  engine/brand.py           brand directory loader + check
  engine/calendar.py        calendar.yaml loader + check
  engine/looks.py           looks loader + check
  skills/catalog.py         SKILL.md discovery, front matter, lessons, sha
  skills/runner.py          the bounded loop; modes; skill_run rows
  skills/toolbelt.py        the fixed tools
  media.py                  the media store: write, read, list, path safety
  render/image.py           an image look rendered headlessly
  render/video.py           the video-ads pipeline, ported
  studio/proposals.py       create, approve, reject, redo, build
  studio/calendar.py        slots over a date range, state, fill
  studio/swipe.py           swipe file, rankings, answers, content queries
  studio/canvas.py          nodes and edges, saved layout
  agents/marketer.py        the daily run
  api/studio_api.py         today, calendar, proposals, canvas
  api/assets_api.py         assets, files, rebuild, feedback
  api/competitors_api.py    companies, swipe, remix, ads, rankings, answers, content
  api/context_api.py        brand, skills, looks
  api/runs_api.py           skill runs, agent runs
```

The toolbelt is the only thing a skill can reach: `brand.read`, `brand.list`, `swipe.read`, `swipe.search`, `calendar.read`, `looks.read`, `assets.read`, `transcript.read`, `image.render`, `video.plan`, `video.render`, `files.write`. No shell, no network, no database handle.

## API contract

Every route is `GET` unless marked. Frontend agents build against exactly this.

```
/api/studio/today                                  last agent run, open proposals, week, building
/api/studio/calendar?from&to                       slots with state
POST /api/studio/calendar/fill {days}              marketer drafts every empty slot in range
POST /api/studio/slots/{date}/{name}/skip

/api/studio/proposals?status&kind                  list
/api/studio/proposals/{seq}                        drafts, evidence, claims, read manifest
PUT  /api/studio/proposals/{seq}/draft {path,text} edit before approving
POST /api/studio/proposals/{seq}/approve           starts a build skill_run, returns its seq
POST /api/studio/proposals/{seq}/reject {reason}
POST /api/studio/proposals/{seq}/redo {note}
/api/studio/canvas?from&to&kind&skill              nodes, edges, frames
PUT  /api/studio/canvas/layout

/api/assets?kind&look&origin&q                     library
/api/assets/{seq}                                  lineage, versions, files, feedback
/api/assets/{seq}/files/{path}                     the bytes
POST /api/assets/{seq}/rebuild {note}
POST /api/assets/{seq}/feedback {text}

/api/competitors                                   tracked companies, per-connector sync
/api/competitors/swipe?competitor&platform&angle&hook&format&sort
/api/competitors/swipe/{id}                        creative, labels with quotes, timeline
POST /api/competitors/swipe/{id}/remix {kind,look,slot,keep}   → a draft proposal
/api/competitors/ads?competitor&platform           counts, longevity, angle mix
/api/competitors/rankings?keyword                  us and each competitor, by week
/api/competitors/answers?prompt                    prompt x engine, who was named
/api/competitors/content                           page changes, posts

/api/brand                                         files, sha, used-by, read counts
/api/brand/{name}                                  body
/api/skills                                        list, modes, lessons, run stats
/api/skills/{name}
POST /api/skills/{name}/run {mode,input,look,slot}  the runner, any caller
/api/looks                                         video and image looks
/api/looks/{name}                                  scenes, limits, used-by
/api/skill-runs?limit&skill&mode                   activity
/api/skill-runs/{seq}                              stages, tool calls, cost
/api/agent-runs?limit
```

MCP gains context tools (`brand.read`, `brand.list`, `competitors.swipe`, `competitors.rankings`, `competitors.content`, `calendar.slots`, `looks.list`, `assets.list`, `assets.read`, `proposals.list`) and one tool per skill (`dw.post`, `dw.newsletter`, `dw.blog`, `dw.image`, `dw.video`, `dw.remix`, `dw.counter_ad`) which runs that skill in chat mode.

## Frontend

`app/studio/`, Vite + React + Tailwind + TanStack Query, copied in shape from `app/dashboard/`. Compose service `studio` on host port 4094. Routes:

```
/                       Today
/calendar               Month · Week · List, slot drawer
/proposals              list; /proposals/:seq  post · video · image variants; build progress
/canvas                 React Flow pinboard, lineage edges
/competitors            Swipe file; /swipe/:id; /ads /search /answers /content /companies
/assets                 Library; /assets/:seq
/context/brand          brand files; /skills /looks /sources /mcp
/activity               Agents · Skill runs
```

The nineteen views are drawn in `marketing-workflows-brainstorm.md`; they are the specification.

## Agent waves

Every agent owns files no other agent in its wave touches. During a wave an agent runs only its own test files; the hub runs the full gate between waves.

**Wave 1** — the spine.

| Agent | Owns |
|---|---|
| W1-A schema | `app/backend/app/models.py`, one alembic migration, `app/backend/app/config.py` |
| W1-B definitions | `definitions/**` except `looks/`, `app/backend/app/engine/{brand,calendar,competitors}.py`, `checks.py` |
| W1-C mock | `mock/**`, fixtures for the four new sources |
| W1-D skills | `.claude/skills/dw-*`, `agents/*.yaml`, `.github/workflows/*` |

**Wave 2** — the backend, and the frontend shell in parallel.

| Agent | Owns |
|---|---|
| W2-A connectors | `app/backend/app/sources/**`, `creds.py`, `catalog.py`, their tests |
| W2-B runner | `app/backend/app/skills/**`, `media.py`, `api/skills_api.py` |
| W2-C looks | `app/backend/app/render/**`, `engine/looks.py`, `definitions/looks/**`, `api/context_api.py` |
| W2-D studio | `app/backend/app/studio/**`, `api/{studio,assets,competitors,runs}_api.py` |
| W2-E frontend shell | `app/studio/**` shell, api client, routes, Today, Calendar, Proposals |
| W2-F frontend views | `app/studio/src/views/**` Canvas, Competitors, Assets, Context, Activity |

**Wave 3** — what needs the rest to exist.

| Agent | Owns |
|---|---|
| W3-A mcp | `app/backend/app/mcp.py`, `api/mcp_api.py`, its tests |
| W3-B marketer | `app/backend/app/agents/**`, the daily run, `api/runs_api.py` |
| W3-C e2e | `app/e2e/studio/**`, compose `studio` service, `test.sh` |

**Wave 4** — the hub, alone: migration proof, README, the full gate, snapshot baselines, the PR.

## Rules every agent carries

- No comments anywhere; the exception is a column comment in `models.py`.
- Red before green: failing tests first, run, committed, then the implementation.
- 100% line and branch coverage; add tests for every branch you write.
- The clock only through `app/clock.py`.
- Never stage `app/.env`, `docs/`, `TODO.md`, or another agent's files.
- Commit subject: one imperative sentence, under 72 characters, the house voice.
- Stack: compose project `os_studio`; postgres 6442, backend 9092, mock 9192, console 4092, dashboard 4093, studio 4094.
- Tests run in the backend container with your own `DATABASE_URL` and the three flags off.

## Wave 4 — the hub pass

In order, after every agent has landed:

1. Verify `app/backend/app/api/routers.py` carries every agent's two lines, and that `HANDLER_MODULES` and `ROUTERS` agree.
2. Reconcile the API contract against `app/studio/src/api.ts` — every gap an agent reported.
3. Merge `origin/main` into `feat/studio` and resolve. Main moved 58 commits (PR #53, real sources) while this was built. Thirteen files overlap:
   `app/backend/app/config.py`, `sources/creds.py`, `sources/paginators.py`,
   `tests/test_checks.py`, `test_connector_pulls.py`, `test_extract_hooks.py`, `test_paginators.py`,
   `app/docker-compose.yml`, `docker-compose.snap.yml`, `definitions/mappings.yaml`,
   `mock/ARCHITECTURE.md`, `mock/server.py`, `README.md`.
   Most are additions in different places. The one to read carefully is `creds.py`: main gave every source a real-credential path, and the six competitor sources need entries in it rather than mock-only ones. Merge commits only, never squash.
4. `./test.sh unit` — ruff, the suite, 100% line and branch coverage.
5. `./test.sh snap-update` — alone, detached, roughly ten minutes; the console, dashboard and studio baselines.
6. `README.md`: the Connectors table gains the Competitors row, the counts move to 33, the Configuration table names every new variable, and the architecture section describes Studio.
7. Prove the demo end to end: sync, rebuild, a draft, an approval, a build, the asset in the library.
8. Open the PR.
