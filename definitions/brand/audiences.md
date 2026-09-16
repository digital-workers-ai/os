---
title: Audiences
updated: 2026-09-15
---
# Audiences

Three readers. Write to one at a time, never to all three in one piece.

## The owner

Runs a small company on a dozen tools. Sales has one Acme, billing has
another, support has a third, and nobody can say which revenue figure is
the real one. Cannot hire a data team and does not want to.

- Wants: one number they can trust, and to know which customer needs attention today.
- Reads: a short post, a morning briefing, a chart with its source under it.
- Cares about: which tool a number came from; whether a target is being hit; what moved since yesterday.
- Do not: explain the architecture; say "pipeline"; promise a feature.
- Open with: a scene they have lived through, then what DW-OS does about it.

## The operator

The person who runs the tools day to day: the office manager, the head
of sales, whoever owns the CRM. Would open the console, work the review
queue, and change a definition line when a tool renames a field.

- Wants: to see what changed, fix a mapping without a developer, and trust a merge.
- Reads: the how; the console pages; the definition files themselves.
- Cares about: the review queue; which value wins when tools disagree; a finding with its evidence attached.
- Do not: reduce their work to "automation"; hide what a rebuild does and does not touch.
- Open with: the concrete task, then how the system carries it.

## The engineer

Evaluates before anyone signs. Will clone the repository, read the
definitions, run the gate, and check the license before replying.

- Wants: to know what runs where, what is deterministic, and what the model is allowed to read.
- Reads: README.md, definitions/, the tests, LICENSE.
- Cares about: AGPL-3.0; Docker on their own machine; 100% line and branch coverage; the model handed finished numbers, never the database.
- Do not: say "AI-powered" without naming the layer and what it reads; round a number.
- Open with: the design decision, then the file that proves it.
