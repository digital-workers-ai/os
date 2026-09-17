---
title: Brand brain
updated: 2026-09-15
---
# Brand brain

Digital Workers is the company. DW-OS is the product. Everything Studio
makes speaks for the one about the other, and every fact it uses has a
row in proof.md.

## What DW-OS is

An AI Operating System for small businesses, built as code the company
owns and evolves. It connects the tools a small company already runs on,
keeps every record exactly as it arrived, rebuilds everything from that
raw store, joins the same customer across tools, and calculates the
numbers the business runs on. Each number reports which tool it came
from, which records it counted, and which of those records were missing
the field.

## How it is made

- Open source under AGPL-3.0, in a public repository.
- Runs on Docker on the company's own machine. Docker is the only requirement.
- 27 connectors across sales and CRM, billing and shops, support, email and lifecycle, advertising, analytics and product, meetings and messaging.
- The business logic is definition files in the repository: what a customer is, which fields matter, how revenue is calculated, what counts as a problem, what the targets are.
- Every start and every rebuild checks the definition files against each other. If they disagree, nothing runs and the message names the file.
- The test gate holds 100% line and branch coverage. Nothing is committed on red.
- The code is generated and reviewed by an engineer before it lands.

## Where AI sits

- Briefings per role are written by a model handed the finished numbers, never the database.
- Ask answers questions over the same reviewed numbers with seven read-only tools and at most eight rounds.
- A nightly agent proposes fixes as GitHub issues with evidence. Nothing is built until a person approves, and a person merges.
- Any AI assistant reads DW-OS through MCP. The access is read-only and every call is logged.
- The model-backed layers are off by default, and each needs its own key.

## What we say

What the system does, in the words of the person who runs it, with the
file or the layer that proves it. A number appears only when proof.md
lists it, exactly as listed.

## What we never say

That the product is autonomous: a person approves, confirms, rejects and
merges. That it connects everything: it connects 27 tools. That a
feature the README lists as future is here. That a number is
approximate: it is exact or it is cut.

## The company

Digital Workers reads every proposal the nightly agent makes about a
customer's system before anything is built. Connecting a company's real
tools is work done with the company; the open repository answers from
stand-ins. Contact: hello@hiredigitalworkers.com.
