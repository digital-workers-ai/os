# TODO

- [ ] Snapshot metrics automatically at the end of every rebuild (`engine/run`), so history accrues without an operator action. Today `POST /api/metrics/snapshots` is the only writer; series charts and trend goals (`not enough history to judge a trend`) stay empty until someone calls it. The console's "Snapshot now" button was removed pending this.
