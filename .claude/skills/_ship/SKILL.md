---
name: _ship
description: Run the test gate, branch, commit with the rationale in the body, push, open the PR, and watch CI
user-invocable: true
argument-hint: "[branch-name] [--draft]"
---

# Ship

Commit the current changes on a branch, push, and open a pull request. This is the os repo itself: every command runs from the repo root, nothing is prefixed.

## Steps

1. Know what changed. The conversation is the primary source; git confirms it. Run together: `git status` (never `-uall`), `git diff`, `git diff --cached`, `git log --oneline -8`.

2. Run the gate.

   ```bash
   ./test.sh unit
   ```

   Ruff (check and format), the suite, and the 100% line and branch coverage gate. If any of it fails, stop and report what failed; nothing is committed on red. `./format.sh` applies what ruff can fix.

3. Pick the branch. Never commit to `main`. On `main`, create a branch. On another branch, when a person is driving, ask "Commit here, or a new branch `<name>`?" and wait; never switch branches without asking. Use the argument if one was given, else derive a short name with one of these prefixes:

   - `feat/`, `fix/`, `chore/`, `docs/`
   - `operator/` — reserved for the operator's build runs, as `operator/issue-<N>-<slug>`

4. Commit. `git checkout -b <branch>` when new. Stage deliberately: the files of this change, nothing unrelated, never `app/.env` or a key. Ask before folding in unrelated edits. Write the message in a HEREDOC:

   - Subject: imperative, under 72 characters, a sentence about what the system now does. The house voice is in `git log --oneline -8`, e.g. "The app reads the calendar through one seam, and every suite pins it".
   - Body: the rationale. The code carries no comments, so the why lives here or nowhere.
   - No mandated trailer. A harness that requires one appends it.

5. Push and open the PR. `git push -u origin <branch>`, then, with `--draft` when it was passed:

   ```bash
   gh pr create --title "<imperative, under 70 characters>" --body "$(cat <<'EOF'
   ## Changes

   - <what changed, and why>

   ## Test checklist

   - [ ] `./test.sh unit` — green, 100% line and branch coverage
   - [ ] <what the reviewer does, and what they should see>
   EOF
   )"
   ```

   Changes: one bullet per logical change, not per file, what and why, under 10. Test checklist: one checkbox per verifiable change, the first one the demo or test command. Never a session URL in the body.

6. Watch CI and fix red before you report.

   ```bash
   gh run watch --exit-status "$(gh run list --branch <branch> --limit 1 --json databaseId -q '.[0].databaseId')"
   ```

   A red run is diagnosed, fixed through a delegated agent (`CLAUDE.md`), pushed, and watched again. `main` requires the `unit` check; the `snapshots` job fails on any pixel the console moved, which means the baselines are missing from the PR.

7. Report the PR URL.

## Updating a PR

`gh pr edit` fails on this repo (a GraphQL deprecation). Use the REST endpoint:

```bash
gh api repos/digital-workers-ai/os/pulls/<N> -X PATCH -f title="..." -f body="..."
```

## Merge policy

Merge commits only, never squash. Carlos reviews and merges every PR. Auto-merge, `gh pr merge --merge --auto`, only when he says so. Delete-branch-on-merge is on: a merged branch is gone, so the next change branches fresh from `main`.
