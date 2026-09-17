---
title: Proof
updated: 2026-09-15
---
# Proof

Every claim Studio may make, with the file in this repository that
proves it. A claim with no row here is not made.

| Claim | Source |
|---|---|
| DW-OS is an AI Operating System for small businesses, built as code the company owns and evolves | README.md, opening line |
| Digital Workers makes DW-OS | README.md, "An Engineer in Your Loop" and "Contact" |
| Connects 27 tools | README.md, "Connects 27 ..." and the Connectors table |
| The 27 span sales and CRM, billing and shops, support, email and lifecycle, advertising, analytics and product, meetings and messaging | README.md, Connectors table |
| Open source under AGPL-3.0 | LICENSE; README.md, "License" |
| Runs on Docker on the company's own machine; Docker is the only requirement | README.md, "Quickstart"; CONTRIBUTING.md, "Setup"; app/docker-compose.yml |
| Every number reports which tool it came from, which records it counted, and which of those records were missing the field | README.md, "Introduction" |
| Nothing is a black box; the same data always gives the same answer | README.md, "Introduction" |
| Raw data is kept exactly as it arrived; nothing there is edited or deleted; everything else is rebuilt from it | README.md, "Architecture", layer 2 |
| A rebuild never touches the raw store, the snapshots, what the AI parts wrote, or the review decisions people made | README.md, "How a Rebuild Works" |
| The definition files are ontology, mappings, transforms, synonyms, derived, metrics, rules, goals, dashboards and enrichment | definitions/; README.md, "Your Business as Code You Own" |
| The definitions are checked against each other at every start and every rebuild; if they disagree, nothing runs and the message names the file | README.md, "Your Business as Code You Own"; app/backend/app/engine/checks.py |
| The test gate holds 100% line and branch coverage; nothing is committed on red | CONTRIBUTING.md, "The gate"; test.sh |
| The code is generated and reviewed by an engineer | README.md, the note under the opening list |
| Look-alike records go to a review queue; a person confirms, rejects or splits them | README.md, "Architecture", layer 8 |
| When tools disagree, the most recently changed value wins by the tool's own clock, then the higher-ranked tool, then a fixed order | README.md, "Architecture", layer 9 |
| Snapshots are the only history and are never deleted | README.md, "Architecture", layer 16 |
| Briefings are written by a model handed the finished numbers, never the database | README.md, "Introduction" |
| Ask uses seven read-only tools and at most eight rounds | README.md, "Architecture", layer 19; app/backend/app/config.py |
| Every model-backed layer is off by default and needs its own key | README.md, "Configuration" |
| Any AI assistant reads DW-OS through MCP; the access is read-only and every call is logged | README.md, "MCP Support" and layer 24; app/backend/app/mcp.py |
| A nightly agent proposes fixes as GitHub issues with evidence; nothing is built until a person approves; a person merges | README.md, "The Nightly AI Engineer Agent"; .github/workflows/operator.yml; .github/workflows/operator-build.yml |
| The operator never commits, never branches, and never approves itself | README.md, "The Nightly AI Engineer Agent" |
| Digital Workers reads every proposal the nightly agent makes before anything is built | README.md, "An Engineer in Your Loop" |
| The dashboard installs as an app; the shell is cached, the numbers never are | README.md, "The Dashboard" |
| The open repository answers from stand-ins, not live accounts; connecting real tools is work done with the company | README.md, "Connectors" |
| Deletions upstream are not detected; a record that disappears from a tool stays in the graph | README.md, "Connectors" |
| Workflow support is future, not present | README.md, the note under the opening list |
| Contact is hello@hiredigitalworkers.com | README.md, "Contact" |

## Using a number

- State it exactly as the source states it. 27 is 27, never "nearly 30", "dozens" or "25+".
- Never turn a fact into a benefit it does not support. 27 connectors does not mean "connects everything"; a review queue does not mean "no duplicates".
- A claim with no row here is cut, not softened.
- A number the sources state two different ways is not a proof. Cut it, and open an issue naming both places.
- When a source changes, this table changes in the same pull request.
