---
name: _add-tests
description: Write the failing tests for a change before it is built, hold coverage at 100% line and branch, and report every test touched
user-invocable: true
argument-hint: "[what to test, or empty for what the conversation just changed]"
---

# Add tests

Test what `$ARGUMENTS` names, or what the conversation just changed.

## Rules

- Red before green. The failing test is written, run and committed before the implementation, as its own commit, so red is visible in history (`CLAUDE.md`). A test that passes before the implementation exists is testing nothing; fix it.
- 100% line and branch coverage is machine-enforced: `./test.sh unit` runs pytest with `--cov-branch --cov-fail-under=100`. Every new branch gets a test. A coverage pragma is a comment, and comments are not allowed, so restructure the code instead of excluding it.
- Never remove an existing test. Never silently change one: a modified test is reported as before / after / why.
- Every test runs with the clock pinned at `2026-09-04T12:00Z`, an autouse fixture in `conftest.py`; the app reads time only through `app/clock.py`, so `as_of`, window bounds and app-written timestamps are exact in assertions.

## Steps

1. Detect the mode. No implementation yet is the normal case: red first. Implementation already in the tree: still add the tests, and say in the report that they were written after the code.

2. Read the neighbours before writing. Backend tests live in `app/backend/tests/`:

   - `test_<module>.py` — pytest, async by default (`asyncio_mode = "auto"`)
   - `test_properties.py` — hypothesis property suite
   - `test_api_contract.py` — schemathesis over the live OpenAPI; `e2e`-marked, because unit-suite DB contention manufactures false 500s
   - `e2e/` — `e2e`-marked, runs against the live mock estate
   - `live/` — `llm`-marked, calls the real Anthropic API; needs a key, never in CI

   `./test.sh unit` runs `not e2e and not llm`; `./test.sh e2e` runs `e2e and not llm`.

3. Plan: one line per test with the file and what it pins. Every branch of the change appears here.

4. Write the tests. A new file is `test_<feature>.py` with the fixtures its siblings use; no docstrings, no comments (`CLAUDE.md`). One thing per test, and the name says which.

5. Run the red on the subset:

   ```bash
   docker compose -f app/docker-compose.yml exec -T backend python -m pytest tests/test_x.py -v --tb=short
   ```

   Each new test fails on an assertion or a missing name, not on a broken import elsewhere. Commit the red on its own.

6. After the implementation, run the subset green, then the gate:

   ```bash
   ./test.sh unit
   ```

## Running beside other agents

- Several agents running pytest at once share one database and manufacture failures. Give each its own: add `-e DATABASE_URL=postgresql+asyncpg://os:os@postgres:5432/os_<agent>` to the `exec`. Only a solo run's coverage number counts.
- A developer's `app/.env` may switch model flags on, which flips the off-state tests. Pass `-e COACHING_ENABLED=false -e ENRICHMENT_ENABLED=false -e CONVERSATION_ENABLED=false` on the `exec` when that happens.

## Frontend

`app/frontend/` has no unit runner. It is covered by the Playwright snapshot suite: `./test.sh snap` builds a fresh stack, syncs, rebuilds, seeds, and compares every page against the committed baselines with zero pixel tolerance; `./test.sh snap-update` rewrites the baselines. Run it alone, never overlapping the unit suite, and never inside a tool's 10-minute timeout: it takes about nine minutes on a fresh stack, so run it detached (`nohup ./test.sh snap > snap.log 2>&1 &`) and read the log. A console change ships with its updated baselines in the same PR.

## Report

```
Tests added: <n> in <files>
Tests modified:
- <file>::<test> — before: <x> / after: <y> / why: <z>
Suite: ./test.sh unit — <passed>/<total>
Coverage: <the coverage line>
```

Say when the tests were written after the code. Then hand off to `_ship`.
