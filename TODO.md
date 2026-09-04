# TODO

- [ ] Snapshot metrics automatically at the end of every rebuild (`engine/run`), so history accrues without an operator action. Today `POST /api/metrics/snapshots` is the only writer; series charts and trend goals (`not enough history to judge a trend`) stay empty until someone calls it. The console's "Snapshot now" button was removed pending this.
- [ ] Enrich automatically at the end of every rebuild (`engine/run`), right after the metrics snapshot: read every eligible entity not yet read under the current vocabulary (`enrichment/store.enrich`), so transcripts get their labels without an operator action; when `ENRICHMENT_ENABLED` is off the step is a no-op. Today `POST /api/enrichment/run` is the only trigger. The console's Run / force / limit controls were removed pending this.
