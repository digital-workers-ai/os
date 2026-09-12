# Contributing

## Setup

Docker Desktop is the only requirement on the host, plus `python3` for the search-vocabulary check that `./test.sh unit` runs before the suite.

```
cp app/.env.example app/.env
docker compose -f app/docker-compose.yml up -d --build --wait
curl -X POST localhost:8092/api/sync
curl -X POST localhost:8092/api/rebuild
```

The example env is empty and that runs: every knob has a default. The compose project is `os`: postgres on :5442, the mock providers on :8192, the backend on :8092, the console on :3092. The Configuration section of `README.md` lists every variable.

## The gate

```
./test.sh unit           ruff check + ruff format --check, then pytest at 100% line and branch coverage
./test.sh e2e            the e2e-marked suite against the live mock providers
./test.sh snap           Playwright screenshots of every console page against the committed baselines
./test.sh snap-update    accept new baselines
./format.sh              apply what ruff can fix
```

`unit` runs inside the backend container and starts the stack when it is down. `snap` builds a fresh stack under its own compose project: run it alone, never overlapping the unit suite, whenever anything under `app/console/` changes, and ship the updated baselines in the same PR. Nothing is committed on red.

## Rules

**No comments.** No `#` comments, no docstrings, no YAML, shell or TOML comments. Code explains itself through naming and structure; commit messages and PR descriptions carry the rationale. The one exception is the DB schema in `app/backend/app/models.py`: every column gets a trailing comment, five words at most plus two or three example values.

**Minimalism.** Ship only what the change needs: no speculative fields, flags, endpoints or config. Anything aspirational, an invariant not yet enforced or a knob nothing reads, waits for the PR that enforces or reads it.

**The clock.** Every test runs with the clock pinned at `2026-09-04T12:00Z`, an autouse fixture in `conftest.py`. The app reads the calendar only through `app/clock.py`, and ruff refuses any other wall-clock read.

**Red before green.** The failing tests are written, run and committed before the implementation, as their own commit, so red is visible in history. A test that passes before the implementation exists is testing nothing. Never remove an existing test; a modified test is reported as before, after and why.

**Size.** Every change is a PR of at most 1–2k lines, tests included.

## Schema changes

The schema is a chain of Alembic migrations in `app/backend/alembic/versions/`, run to head at boot, so a fresh database, the test database and a restored snapshot all reach the checkout's head with no extra step.

1. Change the model in `app/backend/app/models.py`.
2. Generate the migration; never hand-write one.
3. Read the whole generated file.
4. Prove it: upgrade head, downgrade one, upgrade head.

```
docker compose -f app/docker-compose.yml exec -T backend alembic revision --autogenerate -m "<what changes>"
docker compose -f app/docker-compose.yml exec -T backend alembic upgrade head
docker compose -f app/docker-compose.yml exec -T backend alembic downgrade -1
docker compose -f app/docker-compose.yml exec -T backend alembic upgrade head
```

Autogenerate also picks up drift; anything not part of the change is a question for the reviewer, not something to keep quietly. Never edit a migration that has been applied anywhere; add a new one. `test_migrations.py` fails when head and the models disagree.

## Branches and pull requests

Never commit to `main`. Branch with one of `feat/`, `fix/`, `chore/`, `docs/`; `operator/issue-<N>-<slug>` is reserved for the operator's build runs. Stage only the files of the change, never `app/.env` or a key. The commit subject is one imperative sentence about what the system now does; the body is the rationale, because the code carries none. Merge commits only, never squash. The `unit` check must pass before a person merges.

## Working with agents

The `dw-*` skills under `.claude/skills/` are the in-repo workflow for Claude Code:

- `dw-implement` plans the change and builds it red before green
- `dw-add-tests` writes the failing tests and holds coverage at 100%
- `dw-ship` runs the gate, branches, commits and opens the PR
- `dw-operator` and `dw-operator-build` are the daily operator agent's rules

## Reporting

Bugs and feature requests go through the issue forms. Security reports follow `SECURITY.md`, never a public issue. `CODE_OF_CONDUCT.md` applies to every interaction in the project.
