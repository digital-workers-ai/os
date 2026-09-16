---
title: Objections
updated: 2026-09-15
---
# Objections

Five things a reader says back. Each answer is what is true, in the
words of proof.md. Nothing here promises what the product does not do.

## 1. "We already have a dashboard."

A dashboard shows a number. DW-OS shows the number, which tool it came
from, which records it counted, and which records were missing the
field. The definitions are versioned in a repository, so when a number
moves you can tell whether the business moved or the definition did. A
dashboard cannot answer that.

## 2. "An AI will make things up."

The briefing model is handed finished numbers, never the database, so
it can word them but not invent them. Ask uses seven read-only tools and
at most eight rounds. The nightly agent opens an issue with evidence,
nothing is built until a person approves, and a person merges. MCP
access is read-only and every call is logged.

## 3. "Our data will leave the building."

DW-OS runs on Docker on the company's own machine, in a Postgres the
same compose stack starts there. The model-backed layers are off by
default and each needs its own key. When one is switched on, it sends
the model that layer's input: finished numbers for a briefing, the text
it reads for enrichment.

## 4. "We would be locked in."

The code is open source under AGPL-3.0. The definition files that
describe the business are plain files in the company's repository. Raw
data is kept exactly as it arrived from each tool, so nothing is
reshaped into a format only DW-OS can read.

## 5. "We are too small for this."

Docker is the only requirement, and every setting has a default, so an
empty configuration runs. The open repository answers from stand-in
data; connecting a company's real tools is work Digital Workers does
with the company. What it connects today: 27 tools across sales,
billing, support, marketing, analytics, meetings and messaging.

## When there is no answer

Deletions upstream are not detected: a record that disappears from a
tool stays in the graph. Workflow support is listed as future. Say so.
