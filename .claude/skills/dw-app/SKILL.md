---
name: dw-app
description: Build a custom app for DW Apps from a description or an approved app issue — the app.yaml, its ontology, mappings, rules and sample records, a script or a screen only when the vocabulary can't say it — try it on the samples and ship it through dw-ship
user-invocable: true
argument-hint: "<what the app is for, or the number of an approved app issue>"
---

# Build a custom app

Take the app from `$ARGUMENTS`: a description of what a business needs, or the number of a GitHub issue labelled `app` and `approved`. If neither says what the app is for, ask.

A custom app is one file, `definitions/apps/<app_name>/app.yaml`, checked at boot and before every rebuild with the other definitions. DW Apps draws it on the phone: a person takes a photo, uploads a PDF, scans a code or holds to talk, the model reads what it can into the fields, the person fixes what's wrong and saves. A saved record is a raw event of the `custom` source, and the rebuild maps it into ontology entities that metrics, rules, Ask and search already handle.

Run without anyone watching (from `.github/workflows/app-build.yml`), there is nobody to answer questions: the issue is the brief, and every choice you make is written down as an assumption.

## Steps

1. Read what is already here before writing a word:
   - every `definitions/apps/*/app.yaml`, for the shapes that already work;
   - `definitions/ontology.yaml`, for the entities a record can land as or look up;
   - the `custom.*` lines in `definitions/mappings.yaml`;
   - `definitions/rules.yaml`;
   - the readings in `definitions/enrichment.yaml`, whose labels `labels_from` reuses;
   - the scripts in `app/backend/app/custom/apps/*/script.py` and the screens in `app/custom/src/apps/*/screen.tsx`;
   - the seeded records in `app/backend/fixtures/custom/records.yaml`.

   For an issue, read it whole with `gh issue view <N> --comments`. The body holds `## Conversation`, every message of the chat in order under `### Person` or `### Builder`, and `## Draft`, the final app.yaml in a yaml block already checked by `engine/apps.py`; the comments may revise either. An issue titled `Change app: <title>` opens with `## App`, the name of the app it changes: change that app and what it lands in, rather than adding a new one.

2. Ask every open question in one round, never one at a time: who opens the app and its records (its `roles`), what the person photographs, uploads, scans or says (its `input`), which fields it needs and the labels of each choice, which existing records a lookup finds and by which attribute, what it should land as, and what should raise a flag. Leave out what the description or the issue already settles. With nobody there to answer, choose the plainest reading, keep going, and note each choice as an assumption.

3. Write the app and everything it lands in:
   - `definitions/apps/<app_name>/app.yaml`, with the vocabulary below and no comments. The folder name is the app name, in snake_case, and so is every role and label.
   - `definitions/ontology.yaml`: the entity the app lands as, with an attribute per field and a description. Each list, grid row, grid cell or checklist item lands as a child entity carrying a `<parent>_ref` attribute, linked by a `belongs_to` relationship `via:` that ref. A lookup lands under the looked-up attribute's name, and links through a `match:` relationship on it only when that value identifies exactly one entity in the estate, as an identity attribute such as a code, SKU or email does; otherwise it stays a plain text attribute with no link, as products looked up by name do, since each store holds its own copy. Money lands as `amount` with a `currency`; a second money field, and money on a child, lands as a plain number. Reuse an entity when one fits, and keep a label meaning one thing everywhere.
   - `definitions/mappings.yaml`: one line per field. A field of the record is `custom.<app_name>.<field>`. A list row's field is `custom.<app_name>._<list>_<field>`, a grid row's `_rows_<field>`, a grid cell's `_cells_<field>` and a checklist item's `_items_<field>`. Each child maps `_<list>_parent`, `_rows_parent`, `_cells_parent` or `_items_parent` to its `<parent>_ref`, and its keys (`_rows_row`, `_cells_row`, `_cells_column`, `_items_section`, `_items_item`) to attributes of their own. An app with money maps `custom.<app_name>.currency: currency`. A `filled_by: script` field needs its line too.
   - `definitions/transforms.yaml`: a transform for any new identity attribute and any new money label.
   - `definitions/rules.yaml`: a rule for each thing the answers say should raise a flag.
   - Two saved sample records in `app/backend/fixtures/custom/records.yaml`, with their files in `app/backend/fixtures/custom/samples/`, and the app's payloads in `app/backend/fixtures/mock/custom/` with what they extract in `expected.json`. Samples are synthetic: invented receipts, invoices, checks, clips and codes, never a real document.

4. Bring code only when the vocabulary can't say it, and test it:
   - Logic goes in `app/backend/app/custom/apps/<app_name>/script.py` (with an `__init__.py`), named by `script: script.py`. It exposes `async def fill(record, ctx) -> dict` and fills only the `filled_by: script` fields. `ctx.previous(where)` returns the latest earlier record of the same app whose fields equal `where`; `ctx.entity(entity_type, by, value, attr)` returns a current attribute of an entity. Its tests go in `app/backend/tests/test_custom_app_scripts.py`, and coverage stays at 100% line and branch.
   - A field the runtime can't draw (a signature box, a map) is `type: screen` with `file: screen.tsx`, written at `app/custom/src/apps/<app_name>/screen.tsx`. It takes the field's value and returns the new one. Its e2e goes under `app/e2e/custom/`.

5. Try it on the samples. `./test.sh unit` runs the apps check, the fixture replay and the scripts. Seed the demo records, rebuild, open DW Apps on port 3097, and walk one sample through: the fields it reads, the record it saves, the entity it becomes after Rebuild, the rule that fires. Fix what the samples show before shipping.

6. Ship through `dw-ship`. A PR built from an issue says `Closes #<N>`, and its body lists every assumption under `## Assumptions`, so the reviewer sees each choice nobody was asked about.

## Vocabulary

| Name | What it says |
|---|---|
| `title` | What the app is called, on the phone and in the console. Required. |
| `description` | What the app is for. It is also what the model is told it is reading, so a limit goes here: "never read the account number". |
| `input` | How a record starts: one of the inputs below, or a list of them in the order the screen offers them. Required. |
| `roles` | The snake_case roles that may open the app and its records. `admin` always may. |
| `lands_as` | The ontology entity each saved record becomes. |
| `fields` | What is read, scanned or typed, by name, in the order the screen shows them. |
| `template` | A `grid` (rows by columns, like a perio chart) or a `checklist` (sections of items). Each row, cell or item lands as a child entity. |
| `script` | `script.py`, the app's own logic in `app/backend/app/custom/apps/<app_name>/`, run on each save. |
| `photo` | As an input, a photo taken on the phone (up to 10 a record). As a field, a photo attached to the record or to one item. |
| `pdf` | One PDF of up to 100 pages. |
| `scan` | A QR code or barcode, scanned on a tap or typed. |
| `voice` | Hold to talk: one utterance a hold, transcribed on the server. |
| `text` | Free text. |
| `number` | A number, with an optional `unit`. |
| `money` | An amount; the record carries its currency. |
| `date` | A calendar date. |
| `one_of` | One label from `labels`, or from `labels_from`. |
| `many_of` | Any number of labels from `labels`, or from `labels_from`. |
| `lookup` | An existing record: `entity`, and `by`, the attribute a scanned code or a spoken name matches. |
| `list` | Repeated items, with their own `fields` and `lands_as`. |
| `screen` | A field drawn by the app's own `screen.tsx`. |

## Field options

- `type` is required, and is one of the field types above.
- `description` says what the model should read into the field.
- `labels` is a list, or a mapping of label to meaning when a label needs explaining. `labels_from: <reading>.<field>` reuses a reading's labels from `enrichment.yaml` instead.
- `unit` goes with a number.
- `entity` and `by` go with a lookup; `history: true` shows the record's earlier records of this app.
- `from: scan` puts the scanned code in the field, and needs `scan` among the inputs.
- `filled_by: script` leaves the field to the script, and needs `script`.
- `fields` and `lands_as` go with a list; `file: screen.tsx` goes with a screen.
- A grid has `rows` (`name`, `values` as a list or a range like `1-32`, `lands_as`, `fields`), `columns` (`name`, `values`) and `cells` (`lands_as`, `fields`). A checklist has `sections` (each a list of items) and `items` (`lands_as`, `fields`).

Every record also gets, with nothing to declare: when and by whom it was recorded, the files exactly as they arrived, the transcript for voice, and an audit row for every view, edit and removal.
