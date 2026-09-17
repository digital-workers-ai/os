---
title: Pillars
updated: 2026-09-15
---
# Pillars

Four things DW-OS is built on. Each pillar is one line, then the facts
that earn it. Anything we publish stands on at least one of them.

## 1. Every number can be traced

Which tool it came from, which records it counted, and which of those
records were missing the field.

- Nothing is a black box; the same data always gives the same answer.
- A metric is defined once and calculated on request, over any date range.
- Snapshots are the only history, and they are never deleted.
- Because the definitions are versioned, a moving number can be traced to a business change or a definition change.

## 2. Raw data kept as it arrived

Every data point from every tool is stored exactly as it came in, and
everything else is rebuilt from it.

- Nothing in the raw store is edited or deleted.
- A rebuild wipes the derived layer and recomputes it from the raw store.
- Four things a rebuild never touches: the raw store, the snapshots, what the AI parts wrote, and the decisions people made in the review queue.
- When tools disagree, the most recently changed value wins, by the tool's own clock.

## 3. Business as code you own

What a customer is, how revenue is calculated, what counts as a problem
and what the targets are live in definition files in a repository the
company owns.

- Open source under AGPL-3.0.
- Runs on Docker on the company's own machine.
- The definition files are checked against each other at every start and every rebuild; if they disagree, nothing runs.
- A tool renames a field and a mapping line changes; a new status appears and a synonym line folds it in.

## 4. A person approves

AI proposes; a person decides; nothing changes on its own.

- The nightly agent opens a GitHub issue per proposal, with evidence and a plan.
- Nothing is built until a person approves; a person merges the pull request.
- The operator never commits, never branches, and never approves itself.
- Look-alike records go to a review queue where a person confirms, rejects or splits them.
- Briefings are written from finished numbers, never from the database.
- MCP access is read-only, and every call is logged.
