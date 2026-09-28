---
title: Proof
updated: 2026-09-27
---
# Proof

Every claim Studio may make, with the file in this repository that
proves it. A claim with no row here is not made.

| Claim | Source |
|---|---|
| DW-OS is a company operating system for small businesses: AI agents do the routine work, a person approves every change, and the business is code the company owns | README.md, opening line |
| Digital Workers makes DW-OS | README.md, "Contact" and "License"; docs/agents.md, "An engineer in your loop" |
| Connects 40 tools | README.md, the opening list; docs/connectors.md, "All 40 sources" |
| The 40 span CRM and sales, billing, support, marketing, advertising, analytics and spreadsheets, plus 13 sources that watch the brand and its competitors | docs/connectors.md, "All 40 sources" |
| Open source under AGPL-3.0 | LICENSE; README.md, "License" |
| Runs on Docker on the company's own machine; Docker is the only requirement | README.md, "Quickstart"; CONTRIBUTING.md, "Setup"; app/docker-compose.yml |
| Every number can be traced to its tool, its raw fields, how many records went into it, and how many were missing the field | README.md, "Principles"; docs/architecture.md, "Metrics" |
| The same data always gives the same answer | README.md, "What it is"; docs/architecture.md, "The rebuild" |
| Raw data is kept exactly as it arrived; nothing there is edited or deleted; everything else is rebuilt from it | README.md, "Principles"; docs/architecture.md, "Sync and the raw store" |
| A rebuild never touches the raw store, the snapshots, what the AI parts wrote, or the review decisions people made | docs/architecture.md, "The rebuild" |
| The 13 definition files are ontology, mappings, transforms, synonyms, derived, metrics, rules, goals, enrichment, prompts, dashboards, spy and calendar | definitions/; docs/definitions.md, "The files" |
| The definitions are checked against each other at every start and every rebuild; if they disagree, nothing runs and the message names the definition and the key | docs/definitions.md, "Build checks"; app/backend/app/engine/checks.py |
| The test gate holds 100% line and branch coverage; nothing is committed on red | CONTRIBUTING.md, "The gate"; test.sh |
| The code is generated and reviewed by an engineer | README.md, the note under the opening list |
| Look-alike records go to a review queue; a person confirms or rejects each pair, and can unmerge a confirmed one | docs/architecture.md, "Entity resolution"; docs/console.md, "Entities" |
| When tools disagree, the most recently changed value wins by the tool's own clock, then the higher-ranked tool, then a fixed order | docs/architecture.md, "Survivorship" |
| Snapshots are the only history and are never deleted | docs/architecture.md, "Snapshots" |
| Briefings are written by a model handed the finished numbers, never the database | docs/agents.md, "Briefings" |
| The ask agent uses seven read-only tools and at most eight model calls per question | docs/agents.md, "Ask"; app/backend/app/config.py |
| Every model-backed layer is off by default and needs its own key | README.md, "What is on out of the box"; docs/configuration.md |
| Any AI assistant can use DW-OS through MCP; its data tools are read-only and every call is logged | docs/mcp.md; app/backend/app/mcp.py |
| A nightly agent proposes fixes as GitHub issues with evidence; nothing is built until a person approves; a person merges | docs/agents.md, "Operator" and "Builder"; .github/workflows/operator.yml; .github/workflows/operator-build.yml |
| The operator opens issues only: it cannot commit, push or open pull requests, and it never applies the approval itself | docs/agents.md, "Operator" |
| Digital Workers reads every proposal the nightly agent makes before anything is built | docs/agents.md, "An engineer in your loop" |
| The dashboard installs as an app; the shell is cached, the numbers never are | docs/dashboard.md, "Installing it" |
| Every connector answers from a stand-in until its keys are set; connecting the tools without a real-API path is work done with the company | docs/connectors.md, "Real API or stand-in" |
| Deletions upstream are not detected; a record that disappears from a tool stays in the graph | docs/connectors.md, "Limits"; docs/architecture.md, "Sync and the raw store" |
| Workflow support is future, not present | README.md, the note under the opening list |
| Contact is hello@hiredigitalworkers.com | README.md, "Contact" |

## Using a number

- State it exactly as the source states it. 40 is 40, never "nearly 50", "dozens" or "35+".
- Never turn a fact into a benefit it does not support. 40 connectors does not mean "connects everything"; a review queue does not mean "no duplicates".
- A claim with no row here is cut, not softened.
- A number the sources state two different ways is not a proof. Cut it, and open an issue naming both places.
- When a source changes, this table changes in the same pull request.
