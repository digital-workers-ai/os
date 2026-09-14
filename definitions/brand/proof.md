---
title: Proof
updated: 2026-09-14
---

The only place an asset may take a number from. If a figure is not on this
list, an asset does not state it. Each fact names its source so anyone can
check it in the repository.

## The facts

| Claim | Source |
|---|---|
| 29 tools have a connector, one package each | `app/backend/app/sources/`, the Connectors table in `README.md` |
| The business logic lives in plain definition files a company owns and versions | `definitions/`, the table in `README.md` under "Your Business as Code You Own" |
| The definition files are checked against each other at every boot and rebuild; the system refuses to start when they disagree, naming the file | `app/backend/app/engine/checks.py` |
| Every number reports which tool it came from, which records it counted, and how many were missing the field | metric provenance in `app/backend/app/engine/metrics.py` |
| Raw records are kept exactly as they arrived and everything else is rebuilt from them | the raw store, stage 2 of the architecture diagram in `README.md` |
| A nightly AI agent reviews the system and opens an issue with the evidence; it never commits and never approves itself, and a person applies the label before anything is built | `agents/operator.yaml`, `.github/workflows/operator.yml`, `.claude/skills/dw-operator` |
| A model writes the briefings from finished numbers, never from the database | `app/backend/app/coaching/briefer.py` |
| Every AI layer is off until a person switches it on | the flags in `app/backend/app/config.py`, Configuration in `README.md` |
| Any AI assistant can read the same reviewed numbers over MCP, read-only | `app/backend/app/mcp.py`, MCP Support in `README.md` |
| The test suite runs at 100% line and branch coverage on every change | `./test.sh unit`, `CONTRIBUTING.md` |
| The licence is AGPL-3.0 and the repository is public | `LICENSE`, github.com/digital-workers-ai/os |
| It runs on Docker on the company's own machine | Quickstart in `README.md` |

## Rules for using these

State a number exactly as it appears here. Don't round 29 to 30, and don't
write "dozens of tools".

Don't turn a fact into a benefit it doesn't support. "Every number traces to
its source" is not "never make a wrong decision again."

A competitor count in an asset comes from the estate's own records of what the
public ad libraries showed, not from this file and not from memory.

If a claim needs a number this file doesn't have, the claim gets cut or the
fact gets added here first, with its source.
