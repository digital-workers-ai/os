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

There is no migration step and no schema approval gate. The schema is SQLAlchemy `create_all` at startup, so a new table is a model in the PR that first writes it, and nothing else. `create_all` never alters an existing table: a changed column means resetting the dev volume with `docker compose -p os -f app/docker-compose.yml down -v` and bringing the stack back up. Say so in the PR body when a change needs it. Every column carries its trailing comment, the one exception in `CLAUDE.md`.

## Build

5. Delegate. The main session orchestrates and reviews; every code edit goes to a subagent (`CLAUDE.md`). Launch independent tasks together, each carrying the file paths, the project rules, and the success criterion: `./test.sh unit` green.

6. Red first. The failing tests are written, run and committed before the implementation, as their own commit (`dw-add-tests` has the rules). Then the implementation, then green.

7. Tick the plan as tasks land: `- [ ]` becomes `- [x]`.

8. `./format.sh`, then `./test.sh unit`. Ruff, the suite, and the 100% line and branch coverage gate all pass, or the change is not done. `./test.sh snap` when the console changed, run alone and detached.

## Wrap up

9. Report: what was built, the files, any caveat.

10. Ship with `dw-ship`.
