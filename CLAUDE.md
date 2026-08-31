# Project rules

## Commands

- `./test.sh unit` — lint (ruff check + format --check), then pytest with 100% line+branch coverage enforced; runs inside the backend container
- `./format.sh` — apply ruff autofixes and formatting
- `docker compose -f app/docker-compose.yml up -d --wait postgres backend` — start the stack (project `os_v0`, postgres :5442, backend :8092)

## Comments

- No comments anywhere: no `#` comments, no docstrings, no YAML/shell/TOML comments.
- Code must explain itself through naming and structure.
- Commit messages and PR descriptions carry the rationale instead.
- One exception — DB schema definitions: every column gets a comment with a short explanation (5 words max) plus 2–3 example values, e.g. `# vendor record id: cus_9x2, chan_42`.

## Minimalism

- Ship only what the feature absolutely needs — no speculative fields, flags, endpoints, or config.
- Anything aspirational (an invariant not yet enforced, a knob nothing reads) waits for the PR that enforces or reads it.
- When replicating a v11 module, port its essential behavior, not its incidental surface.

## Workflow

- Every code change is implemented by delegating to parallel subagents; the main session orchestrates and reviews (hub-and-spoke), it does not edit code directly.
- Split independent work across agents launched together; group related micro-tasks into one agent rather than over-parallelizing.
- Each delegation carries full context: file paths, project rules, and explicit success criteria (tests green via `./test.sh unit`).
- Red/green: failing tests are written and run before the implementation; the red state lands as its own commit.
- Every change arrives as a PR of at most 1–2k lines, tests included, shipped via the `_ship` skill.
