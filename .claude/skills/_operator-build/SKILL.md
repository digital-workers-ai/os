---
name: _operator-build
description: Headless build agent for approved operator issues — implements the plan in the issue body, opens or updates the pull request that closes it, replies on the issue. Invoked by .github/workflows/operator-build.yml.
disable-model-invocation: true
---

# Agent: Operator build

Implement the approved plan on an `operator` issue and deliver it as a pull
request. Runs headless: the `approved` label and PR review replace every
interactive stop in the sibling skills. The prompt arrives as `... for issue
<N>. Event: <issues|issue_comment>.`

## Context

The runner has the repository checked out with full history and `app/.env`
copied from `app/.env.example`. There is no database copy here: the plan
carries the evidence, and `./test.sh unit` plus CI are the gate. The three
convention skills you follow:

- `.claude/skills/_implement/SKILL.md`: the plan format you are reading.
- `.claude/skills/_ship/SKILL.md`: branch, commit and PR conventions.
- `.claude/skills/_add-tests/SKILL.md`: red before green, coverage held.

An `issues` event is a fresh approval. An `issue_comment` event on an
approved issue is feedback on work already pushed.

## Steps

1. Read the issue and all comments: `gh issue view <N> --comments`. The issue
   body is the plan. Comments after the `approved` label (or after the LGTM)
   are feedback to apply on top of the plan. An issue with no `## Plan`
   section is a finding: comment
   `Nothing to build here: this issue records a finding for a person to handle.`
   and stop.
2. Look for an open PR:
   `gh pr list --state open --search "issue-<N>" --json number,headRefName`.
   If one exists, `git fetch origin` and continue on its head branch.
   Otherwise `git checkout -b operator/issue-<N>-<slug> origin/main`.
3. Set the committer if unset: `git config user.name "operator"` and
   `git config user.email "operator@users.noreply.github.com"`.
4. Implement exactly the plan, under `CLAUDE.md`: no comments anywhere, ship
   only what the plan needs. Delegating parallel work to subagents is
   allowed; the `Agent` tool is in the allowlist. Follow `_add-tests`: the
   failing test is committed before the change that makes it pass, coverage
   stays at 100% line and branch, and no existing test is removed or
   silently changed. Commits follow `_ship`: imperative subject under 72
   characters, the rationale in the body.
5. Gate: `./format.sh`, then `./test.sh unit` must pass. When anything under
   `app/frontend/` changed, also `./test.sh snap` (about nine minutes; run it
   alone). Both start the compose stack on the runner; that is expected.
6. Push: `git push -u origin <branch>`. New PR: `gh pr create` with `_ship`'s
   body, `## Changes` bullets and a `## Test checklist` whose first item is
   the plan's Verify step, and `Closes #<N>` in the body. Existing PR: push,
   then `gh pr comment <PR>` with what changed.
7. `gh issue comment <N>` with the PR link and a two-line summary.

## Feedback runs

On an `issue_comment` event the PR exists. Apply the newest human comment on
its head branch as one or more commits that name the request in the body,
run the gate again, push, and comment on both the PR and the issue. Feedback
that asks for something outside the plan is answered on the issue, not
built: a person widens the plan by editing the body, then approves again.

## When the gate fails

Fix what the plan covers. If `./test.sh unit` cannot pass without going
beyond the plan, do not push a red branch: stop, and say on the issue what
failed, what the fix would need, and why it is outside the plan. A person
revises the plan or closes the issue.

## Hard rules

- Never merge. A person merges after CI is green.
- Never change the `approved` label.
- Never touch `.github/workflows/` unless the plan says so.
- Never commit secrets or `.env`.
- Never push a branch whose gate is red.
- Never widen the plan. A gap in it is reported on the issue, not filled.
