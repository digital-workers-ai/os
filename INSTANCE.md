# Running OS on another business

## What an instance is

OS is an engine plus data. The engine is the code: the connectors, the pipeline, the checks, the stand-in vendors, the renderer and the web apps under `app/` and `mock/`. The data is the set of files that describe one business: its definitions, the world the stand-ins render from, the captured vendor responses the tests replay, and the Studio sample library. An instance is this repository with those files replaced. The engine does not change; the files do, and `./test.sh instance` proves they fit.

## What an instance supplies

| Path | What it holds |
|---|---|
| `definitions/ontology.yaml`, `metrics.yaml`, `rules.yaml`, `goals.yaml`, `dashboards.yaml`, `derived.yaml`, `enrichment.yaml`, `synonyms.yaml`, `calendar.yaml`, `spy.yaml` | The business as code: entities, numbers, findings, targets, pages, roll-ups, enrichment questions, status spellings, the studio calendar, and the brand, competitors and queries Spy tracks |
| `definitions/brand/` | The seven brand files (`brand-brain.md`, `voice.md`, `pillars.md`, `audiences.md`, `objections.md`, `language.md`, `proof.md`) and `tokens.yaml` with the brand name, colours, fonts and logo |
| `definitions/brand/assets/` | The logo (`.svg`) and the fonts (`.woff2`) that `tokens.yaml` names |
| `definitions/briefs/` | One prompt file per briefing reader |
| `mock/world/data.yaml` | The world every stand-in vendor renders from: companies, people, subscriptions, campaigns, tickets, events, the ER variations, the sales calls, the spy brand, competitors and queries, which must match `definitions/spy.yaml`, with their text pools, and the rows each vendor shows. `WORLD_DATA` in the mock's environment points it at another file |
| `app/backend/fixtures/mock/<source>/` | One directory per source `mappings.yaml` names: a record file per object type (`<object_type>.json`, a list of `{"source_id", "payload"}`) and `expected.json`, what the engine extracts from those records, checked by a person |
| `app/backend/fixtures/studio/` | The Studio sample library: `manifest.yaml` and, per asset, `<dir>/<version>/` holding the files the manifest lists with their byte sizes |
| `README.md`, `LICENSE` | The instance's own |

## What stays untouched

The code under `app/` and `mock/` (other than `mock/world/data.yaml`), and the four parts of `definitions/` that belong to the engine rather than to the business: `mappings.yaml` (which vendor field becomes which fact), `transforms.yaml` (how each label is normalized), `prompts.yaml` (the words a model is given) and `looks/` (the layouts an image can take). The engine checks the definition files against each other, so an ontology attr that no mapping line produces fails `definitions`: declare attrs only for fields a connector already maps.

## Refreshing the fixtures

The fixtures are captured through the connectors from the stand-ins, which render from `mock/world/data.yaml`. After changing the world, run

```
./test.sh fixtures
```

which writes every source's record files to `app/backend/captures/<source>/`. Promote each `app/backend/captures/<source>/` over `app/backend/fixtures/mock/<source>/`, keeping `expected.json`, then run `./test.sh unit`: it replays every fixture directory and fails where `expected.json` disagrees with what the engine now extracts. Update `expected.json` only after reading the difference.

## Proving a tree

```
./test.sh instance
./test.sh instance --names names.txt
```

runs `python -m tools.instance_check` in the backend container. It prints one line per check, `ok` or the failure, and exits non-zero if any check failed.

- `definitions`: the files validate through the checks the backend runs at boot and before every rebuild.
- `world`: the world loads through `seeds.world` (`mock/world/data.yaml`, or the file `WORLD_DATA` names when the check's environment sets it) and holds at least one company, one person, a spy brand and one competitor, and its spy brand, competitors and queries are the ones `definitions/spy.yaml` names: the connectors ask the stand-ins about the handles and queries `spy.yaml` names, so the two must agree.
- `fixtures`: every source `mappings.yaml` names has `fixtures/mock/<source>/expected.json` and a record file for each object type it lists.
- `studio`: `fixtures/studio/manifest.yaml` loads with the seed's own reader and every file it lists exists at the stated byte size.
- `names`: with `--names FILE`, one term per line, no file under `definitions/`, `mock/world/data.yaml`, `app/backend/fixtures/` or `README.md` carries a term: case-insensitive, whole-word for words, substring for domains and emails. Without the flag the line says the scan was skipped. List the template business's names, domains and addresses, not the tools': `mappings.yaml` names every connector. The README is scanned where the backend sees it, beside `definitions/`; the compose file does not mount it there, so a container run scans the other three.

## What the gate does not do

It does not replay a fixture, calculate a number or run the engine's test suite. `./test.sh unit` tests the engine against whatever tree it finds: it passes on a template that still names the old business and fails on an instance whose `expected.json` was never updated, so it is a check on the code, not on the data. `./test.sh instance` is the check on the data.
