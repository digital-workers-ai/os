---
title: Why a rebuild never touches the raw store
description: What a rebuild recomputes, what it leaves alone, and where in the repository each rule lives.
pillar: Raw data kept as it arrived
---
# Why a rebuild never touches the raw store

A rebuild wipes the derived layer and recomputes it from the raw store. Four things it never touches: the raw store, the snapshots, what the AI parts wrote, and the decisions people made in the review queue. `README.md`, "How a Rebuild Works", lists them in that order.

## What raw means here

Every data point from every tool is stored exactly as it came in. Nothing there is edited or deleted. The `raw_event` table in `app/backend/app/models.py` has no update path; the sync writes rows and the engine reads them.

## What a rebuild does

It reads the definition files, checks them against each other, and recomputes entities, facts and metrics from the raw store. If two definitions disagree, nothing runs and the message names the file. `app/backend/app/engine/checks.py` is that check.

## What survives

Snapshots are the only history and are never deleted. A person's decision in the review queue is kept and applied again on the next rebuild. Both are stated in `README.md`, "Architecture", layers 8 and 16.

You can rebuild as often as you like, because nothing you would miss is in the path.
