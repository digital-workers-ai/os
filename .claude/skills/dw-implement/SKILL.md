---
name: dw-implement
description: Plan a change as a checklist at docs/plans/<slug>.md, confirm it, then build it red before green and hand it to dw-ship
user-invocable: true
argument-hint: "<feature description>"
---

# Implement a change

Take the feature from `$ARGUMENTS`, or from what the conversation has been circling. If neither says what to build, ask.

This skill is the plan format and the flow. The two stops below are for a person driving directly. A headless agent replaces them with its own gates: the `dw-operator` skills take the plan from an approved issue and never stop here.

## Plan

1. Read the code the change touches before writing a word of the plan. Ask when the request is ambiguous; a plan built on a guess costs more than a question.

2. Present the summary and wait. One paragraph on what the change does and why, the files it touches with what changes in each, and what is out of scope. For a console change (`app/frontend/`), add a lo-fi ASCII sketch of the view with the new elements marked `← NEW`. Ask "Does this capture it?" and do not write the plan until the answer is yes.

3. Write the plan at `docs/plans/<slug>.md`. `docs/` is working notes and is not committed in this repo.

   ```markdown
   # Feature: <Title>

   ## Summary
   One paragraph: what the change does and why.

   ## Changes

   ### Definitions
   - [ ] <task> — `definitions/synonyms.yaml` — <what changes>

   ### Backend
   - [ ] <task> — `app/backend/tests/test_<module>.py` — <the failing test>
   - [ ] <task> — `app/backend/app/<module>.py` — <what changes>
   - [ ] <task> — `app/backend/alembic/versions/<generated>.py` — the generated migration, read in full

   ### Frontend
   - [ ] <task> — `app/frontend/src/<path>` — <what changes>

   ### Docs
   - [ ] <task> — `README.md` — <what changes>

   ## Notes
   - Edge cases, and what is out of scope.
   ```

   Rules: one line per task, a path on every task, tasks ordered by dependency, empty groups omitted. Every code task has its test task beside it, listed first.

4. Print the task count and ask "Ready to build?". Wait.

## Schema

The schema is a chain of Alembic migrations in `app/backend/alembic/versions/`. The boot runs them to head before the build checks, so a fresh database, the test database and a restored snapshot all reach the checkout's head with no extra step.

To change it:

1. Change the model in `app/backend/app/models.py`. Every column keeps its trailing comment, the one place a comment is allowed.
2. Generate, never hand-write: `docker compose -f app/docker-compose.yml exec -T backend alembic revision --autogenerate -m "<what changes>"`. The post-write hooks strip Alembic's markers and format the file.
3. Read the whole generated file and show it in full before going on. Autogenerate also picks up any drift it finds; anything not part of this change is a question for the reviewer, not something to keep quietly.
4. Prove it both ways through the same `exec`: `alembic upgrade head`, `alembic downgrade -1`, `alembic upgrade head`.
5. `./test.sh unit` runs `test_migrations.py`, which fails when head and the models disagree.

Never edit a migration that has been applied anywhere; add a new one. A table still lands in the PR that first writes it. A database built before migrations existed has every table and no version row: `alembic stamp head` once through the same `exec`, or reset the volume with `docker compose -p os -f app/docker-compose.yml down -v`.

## Build

5. Delegate. The main session orchestrates and reviews; every code edit goes to a subagent. Launch independent tasks together, each carrying the file paths, the project rules, and the success criterion: `./test.sh unit` green.

6. Red first. The failing tests are written, run and committed before the implementation, as their own commit (`dw-add-tests` has the rules). Then the implementation, then green.

7. Tick the plan as tasks land: `- [ ]` becomes `- [x]`.

8. `./format.sh`, then `./test.sh unit`. Ruff, the suite, and the 100% line and branch coverage gate all pass, or the change is not done. `./test.sh snap` when the console changed, run alone and detached.

## Wrap up

9. Report: what was built, the files, any caveat.

10. Ship with `dw-ship`.
