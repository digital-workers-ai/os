# OS

An AI Operating System substrate: it pulls raw data from the tools a company uses, projects it into a clean entity graph, and (in later slices) computes metrics, rules, and goals on top. Deterministic by design — same inputs, same outputs, no model calls in the pipeline.

## Concepts

**Source** — one external tool (HubSpot, Stripe, …). Each has a connector that knows how to pull its API. In development every source is served by the vendored mock estate in `mock/`, 27 providers rendering one shared fictional world.

**Raw event** — one payload exactly as a source returned it, stored append-only in `raw_event`. Nothing is ever edited or deleted here; a record that changes gets a new row. This is the system's ground truth: everything else can be rebuilt from it.

Think of `raw_event` as the enrollment book: every record ever seen is in it, permanently.

**Sync** — one pull attempt for a source (`POST /api/sync`). It records itself in `sync_run` — including refusals, id collisions, and truncations — because a quiet source and a broken one must never look the same.

**Entity** — one thing a single source knows about: a company, a person, a deal. Identity is structural — `(source, entity_type, source_id)` — so the same real-world company known to two tools is, at this layer, two entities.

**Canonical entity** — one real-world thing, merged across tools. Resolution buckets entities on declared identity attributes (a company's domain, a person's email) and records the evidence on every membership (`domain=acme.io`). Survivorship then folds the members' facts into one value per attribute — newest observation wins, declared source priority breaks ties — keeping receipts (winning source, raw event, disagreement count). Blocklists stop false merges: a free-mail domain identifies no company, a placeholder identifies nothing.

**Resolution guards** — the rules that keep merging honest, each aimed at a trap real estates set. Beyond the blocklists: **bucket quarantine** — if one tool has *two of its own records* sharing a "unique" value (two Stripe customers on one domain), that value clearly identifies nobody, so it's disqualified as merge evidence for everyone; this one statistic took company precision from 0.92 to 1.00 on the adversarial corpus. **One record per source** — a cluster never absorbs a second record from the same tool: if HubSpot itself thinks they're two people, we don't overrule it. **Corroboration** — a tenant-scoped id (`external_ref`, marked `identity_scope: tenant` in the ontology) is trusted between two tools only where other evidence confirms they share a numbering scheme; no confirmation means no merge, never benefit of the doubt. The guards are measured, not assumed: a vendored adversarial corpus scores the resolver on every CI run, with floors of 0.99 company / 0.98 person pairwise precision — quietly breaking a guard fails the build.

**Resolution ladder** — what happens to two records that are not tied by an identifier but look like the same person. Names never merge on their own; they can only nominate. A pair whose names look alike *and* whose records agree on a second, independent attribute (a phone, a non-free email domain) becomes a candidate in the review queue, with its evidence attached. A person confirms or rejects. A confirmed pair merges and is kept across rebuilds; a rejected pair is remembered and never shown again unless someone confirms it later; unmerge returns a confirmed pair to the queue. Every rebuild re-checks the evidence behind each confirmed pair and flags the ones whose evidence has gone, so a human decision can outlive its reason but never silently. The queue is also the label set: once a pattern has enough confirmations and no rejections it can be measured on the adversarial corpus and, only then, promoted to automatic.

```
two records, same kind
        │
        ▼
1. shared identifier?  (email, source id, domain)
        │ yes ───────────────────────────────────► MERGE, automatic
        │ no
        ▼
2. names look alike?
        │ no ────────────────────────────────────► two entities
        │ yes
        ▼
3. a second attribute agrees?  (phone, email domain)
        │ no ────────────────────────────────────► two entities
        │ yes
        ▼
4. REVIEW QUEUE  pair + evidence
        │
   ┌────┴─────┐
   ▼          ▼
confirm     reject
   │          │
   ▼          ▼
MERGE       two entities, remembered
(human, survives rebuilds; unmerge sends it back to 4)
   │
   ▼
5. every rebuild re-checks the evidence
        │ still holds ────────────────────────────► keep
        │ gone ──────────────────────────────────► flagged for a look
        │
        ▼
6. confirmations accumulate → measure the pattern → promote to step 1
```

**Candidates, declared** — the ladder is switched on per entity kind in `ontology.yaml`. The person entity reads:

```yaml
person:
  attrs: { email, name, phone, title, external_ref }
  identity: [email, external_ref]
  candidates:
    name: name
    corroborate:
      - phone
      - email_domain
```

Three parts: `identity` is unchanged, it is what merges automatically; `name` names the attribute whose values get compared; `corroborate` lists what can back a name up.

How the engine reads it, per pair of records not already in one cluster:

1. Compare the two `name` values. Not alike: stop.
2. For each corroborator, derive a key from each record and compare.
3. One key agrees: the pair is a candidate, that agreement is its evidence.
4. None agree: stop, two entities.

Keys are normalized so the comparison is honest: `phone` keeps digits only and drops a leading US 1; `email_domain` is a virtual attribute, the part of `email` after the `@`, and it counts only when it isn't a free-mail or placeholder domain, the same blocklist the resolver uses. Anything else listed is compared as plain lowercase text.

How "alike" is decided: names are lowercased, stripped of punctuation and split into words, then compared with Python's `difflib.SequenceMatcher`, which is in the standard library, so no dependency and the same answer on every machine. Its `ratio()` is twice the number of matching characters divided by the total length of both strings, from 0 to 1. Two names are alike at 0.8 or above. Because a first name shortened to an initial scores badly on characters, a second rule catches that case: both names have at least two words, the first words start with the same letter, and one last word is a prefix of the other, at least two letters long; that scores 0.8 flat. Some pairs:

```
carlos chinchilla   carlos chinchilla   1.00   alike
richard hendricks   rich hendricks      0.90   alike
jane smith          j smith             0.82   alike
carlos ch           c chinchilla        0.38   alike by the initial-and-prefix rule
bob chen            robert chen         0.74   not alike (a nickname map would be needed)
carlos chinchilla   maria lopez         0.29   not alike
```

The score is only a nomination. It never merges anything on its own, and a person sees it as the `name` chip on the pair.

Two rules keep it safe: a name alone never counts, and a corroborator alone never counts. Both have to agree. And the build checks refuse a declaration that names an attribute the entity doesn't have.

To extend it, add an attribute to the list. To do companies, give `company` its own block, `name: name` with a corroborator that exists for companies; today they only carry domain, industry and name, and domain is already identity, so companies wait for a corroborator worth trusting.

Five pairs through the ladder:

```
a. Carlos Ch <carlos@acme.io>          C Chinchilla <carlos@acme.io>
   step 1: same email                 → merged automatically; the name kept has a receipt

b. Carlos Ch  +1 415 555 0101          C Chinchilla  +1 415 555 0101
   step 1: no shared id · step 2: alike · step 3: same phone
                                      → queued → confirmed → merged, kept across rebuilds

c. Carlos Chinchilla (no email)        Carlos Chinchilla <carlos@acme.io>
   step 1: no · step 2: alike · step 3: nothing else agrees
                                      → two entities; the first counts as identity_less

d. Bob Chen <bob@acme.io>              Robert Chen <robert@acme.io>
   step 2: alike (nickname) · step 3: same domain acme.io
                                      → queued → rejected: two people at Acme
                                      → remembered, not shown again

e. J. Smith <jane@acme.io>             Jane Smith <jane@acme.io>
   step 1: merged by email long ago, then HubSpot corrects the first to <john@acme.io>
   step 5: the shared email is gone   → flagged; the operator unmerges, or reconfirms
```

**Adversarial corpus** — `mock/adversarial.py`, test-only fixture data the mock server never serves and no production code imports. It lives beside `mock/world.py` and extends it: the same mock universe's companies and people, deliberately corrupted into 890 records across six pretend tools, seeded with 53 collisions — shared agency domains, same-name companies, office mailboxes, recycled ids. Every record carries `.truth`, the id of the real thing it describes, so right and wrong merges are *checkable*, never guessed; fixed random seeds make the corpus byte-identical on every import. The precision test runs each record through the shipped transforms (measuring the real pipeline, not an idealized one), resolves with the real guard settings, and scores the clustering pairwise against `.truth`.

**ER settings** — the resolver's only two knobs, in `app/config.py`, env-overridable per deployment. `ER_BUCKET_CAP` (50): if more than 50 *distinct* tools share one identity value, it's junk — the backstop for the one trap the within-one-source statistic can't see. `ER_ONE_RECORD_PER_SOURCE` (true): the on/off switch for that guard, a boolean because a tenant whose CRM is known to be full of duplicates might legitimately want the resolver to merge through them. The other guards have no knobs on purpose — they compare the data against itself, so there is nothing to calibrate.

**Survivorship** — how many opinions become one answer. When a cluster's members disagree about an attribute (HubSpot: "Acme Corp", Stripe: "ACME Corporation"), the fold picks one value per attribute by a fixed rule: newest observation wins (on the provider's clock), a time tie falls to declared `source_priority`, and a remaining tie falls to stable name order — so a rebuild always picks the same winner. Along the way it counts disagreements (distinct losing values, stamped on the fact), lets a winning clear silence the attribute entirely (an empty field that is *fresher* beats an old value), and stamps receipts on every winner: which source, which raw event, observed when.

**Fact** — one attribute of one entity as asserted by one source: "hubspot says company hs_company_001's domain is acme.io." Each fact keeps its provenance (which raw event asserted it, when the provider observed it). Facts obey the **three-state rule**:
- *absent* — the source never mentioned the attribute: no fact row at all
- *cleared* — the source said "this is empty": a fact row with `is_null` true
- *value* — a normalized value that survived its transform

A value the transform refused (garbage date, non-numeric amount) becomes none of these — it is counted and named in the report, never stored and never turned into a null.

**Derived fact** — a fact about one entity computed from the records that point at it, so a rule or a metric can ask a cross-entity question without a join grammar. `derived.yaml` declares them per entity: a company's `mrr` is `SUM(subscription.mrr)` over the subscriptions linked to it by `belongs_to` where `status: active`; its `open_tickets` is `COUNT(ticket)` over the same edge; a person's `last_meeting_at` is `MAX(meeting.started_at)` over `attended_by`. One declared edge, one aggregate, an optional equality filter — that is the whole grammar, and everything it needs is already in the ontology. They are computed at rebuild, after links are built, and land in `fact_current` like any other current value, but with no member and no raw event behind them: a derived fact is a *computation*, not a source's claim, and the API says so (`derived: true`). The refusals are the ordinary ones: a derived name that shadows a declared attribute of its entity fails the build, and a money sum over sources spanning two currencies writes nothing for that entity and is counted in the report — one company's mixed books cost that company's number, not everyone's. A derived attribute is glossed where every label is — the `attributes:` map — so `open_tickets` reads the same in the derived tab, a dimension list and a rule. Rules and metrics may name them like any attribute (`paying_company_with_open_tickets`, `avg_mrr_per_company`), and provenance walks back through the derivation to the source's raw fields, so the receipt still ends at a provider payload. Dates and numbers stay out of the search index here as everywhere, so today's three derived facts are never indexed.

**Observation time** — every fact carries `observed_at`: when the data changed *according to the provider's own clock* (each connector's `OBSERVED_AT` declares where that timestamp lives in the payload). It exists because "newest observation wins" only works on the provider's clock — on our ingestion clock, whichever source synced last would win every disagreement. When the provider's timestamp is missing or unreadable, ingestion time is used and the substitution is counted in the report, never silent.

**seq, first_seq, minted_seq** — one currency at three levels. `seq` is the raw-event insertion counter, the estate's unambiguous "which came first" (timestamps can't order rows written in one transaction). `first_seq` is a record's earliest seq — when it was *first* seen; edits add higher seqs, so it never moves. `minted_seq` is the founding record's `first_seq` on a canonical entity. Resolution processes records in `first_seq` order and mints the canonical id from the earliest record's key — so editing a record can never re-anchor a cluster or change its id.

**ProjectedEntity / ProjectedFact** — the rebuild's in-memory intermediates, produced by the pipeline before anything is written. A `ProjectedFact` is one normalized value plus everything needed downstream: the numeric form for number attributes, the asserting raw event, the observation time and whose clock it came from, and the seq. A `ProjectedEntity` groups those facts under one `(source, entity_type, source_id)` with its `first_seq` and the `anchor_key` string its database id is hashed from. Resolution, survivorship, and links all operate on these objects; only at the end does the rebuild translate them into `entity` / `entity_fact` rows. They never leave the process — if you're reading the database or the API, you're seeing their persisted results, not them.

**Definition files** — the YAML files in `definitions/` that make the system declarative:
- `ontology.yaml` — what entities exist and what typed attributes each may have. An entity's `identity:` list names which attributes count as merge evidence — `company: [domain]`, `person: [email]`: two records sharing a normalized identity value become one canonical entity. The list is deliberately short: names are never identity (too fuzzy — "Acme Corp" vs "ACME Corporation" is the problem, not the key), vendor ids never (each source's ids are its own), and an entity with no `identity:` list (subscription) is never merged at all — one tool owns it. `source_priority:` orders sources for survivorship tiebreaks; `relationships:` declares the edges links may build and what grounds them.
- `mappings.yaml` — one line per raw field worth keeping: `source.object_type.path → attribute`
- `transforms.yaml` — which normalizer each attribute's values pass through
- `synonyms.yaml` — which provider spellings fold to one canonical status
- `metrics.yaml` — the numbers the estate answers with, as declared aggregates
- `rules.yaml` — the conditions worth a human's attention, as declared predicates
- `goals.yaml` — the targets the business holds itself to, judged by strategies
- `enrichment.yaml` — the questions a model may ask of declared texts, as readings
- `derived.yaml` — the cross-entity facts the rebuild computes, as declared rollups over one edge

Every metric and entity may also carry a `description` and `synonyms`, and `ontology.yaml` carries a top-level `attributes:` map glossing the labels themselves — the one place a name is given a meaning, mapped or derived alike, read by the console, the ask agent, MCP and search, so `revenue` finds the `mrr` metric and nobody has to guess what `external_ref` holds. A label means the same thing everywhere, so it is described once: `derived.yaml` declares how a derived attribute is computed and never what it means. A synonym that collides with a name or another synonym fails the build: an alias that points at two things is worse than no alias.

Adding a field, a metric, or a rule to the system is editing a YAML line, not writing code.

**Metric** — a number computed over the canonical layer, declared in `metrics.yaml` (a definition file like the rest: `mrr` is `SUM(mrr)` over subscriptions where `status: active`). Because metrics run over canonical entities, `COUNT(company)` counts Acme once — not once per tool. Every value carries receipts: the population before the filter, how many rows actually fed the aggregate, who lacked the attribute, and the raw provider fields the number walked in from (`mrr` traces to `stripe.subscriptions._amount_monthly`). The semantics refuse to flatter: a sum of nothing is 0 but an average of nothing is unknown (`None`) — a zero average would read as a measurement that never happened; mixed currencies refuse to aggregate rather than silently sum; and one broken definition errors on its own row without taking the catalog down. Served by `GET /api/metrics`.

A metric can also declare **how it is cut**. `group_by` splits it into buckets — an own attribute (`status`), a date attribute at a `grain` (`started_at` by month), or an attribute one declared hop away (`company.industry`, walked over the `belongs_to` edge). Only edges that cannot fan out are allowed: a breakdown over a one-to-many hop double-counts by construction, so it is refused rather than rounded. Buckets are drawn only from the entities the metric actually measured, and each bucket is re-measured over its own ids — so a ratio stays a ratio and mixed currencies still refuse per bucket — while whatever the breakdown could not place is counted (`ungrouped_entities`, `group_bad_values`) rather than dropped. `window_days` with `window_attr` narrows the population to a span on a date attribute: trailing back from today by default, `forward` for what is coming, with the bounds it used (`window_from`, `window_to`) returned beside the value. The clock is a parameter, serialized as `as_of` on the payload, because "subscriptions started in the last 30 days" has an answer that depends on when you asked. The key set is closed — a `groupby` typo refuses the build rather than being ignored — and only the scalar is snapshotted: a breakdown is a question you ask now, not a series.

**Slicing** (`slice_metric`) — the same grammar handed to a model. The ask agent's seventh tool takes a declared metric and composes it with a dimension, a window, or one equality filter, then runs the composition through the same parser and the same ontology checks the build runs, so the model picks *which declared parts to combine* and never writes an expression. It refuses in the layer's own words: a filter on an attribute the metric already fixes (`mrr` fixes `status: active`) comes back naming the conflict rather than silently overriding it, and a hop over an edge nobody declared is a sentence, not an empty result. Called with only a metric it answers with the scalar and lists what that metric can be split by — each dimension with its type, the edge it walks, and its glossed meaning — so discovery is a tool call rather than a guess. It derives nothing the definitions cannot.

**Snapshot** — one metric's value written down with a timestamp: a diary entry for a number. Live values (`GET /api/metrics`) are always *now* and forget; `POST /api/metrics/snapshots` records every metric as a row, and repeated scheduled calls accumulate the series `GET /api/metrics/history` serves — what charts draw and trend goals judge. Three rules, each from a real bug: only the snapshot route writes history (never a rebuild or a page load — v4's read-triggered snapshots turned history into a graph of how often the dashboard was open); a run that measured nothing stores NULL, not zero, with the row still written ("couldn't measure" and "measured zero" are different claims, and "nothing measured" differs from "nobody ran the job"); a broken metric costs one row, never the snapshot.

**Insights (rules and findings)** — the estate naming what deserves a look. A rule, declared in `rules.yaml`, is a claim about **one entity's own attributes** — "a subscription whose status is `past_due`", "a deal past its own close date" — with a severity meaning *how quickly someone wants to know*, not confidence. Cross-entity questions are deliberately outside the grammar: that needs a join, and the limitation is stated rather than disguised. Evaluating the rules (`GET /api/insights/rules`) produces **findings**, each carrying receipts: the canonical entity, a human anchor, the company it hangs off (walked in through canonical links), and per-condition evidence — for an `is_null` rule, the absence itself is the evidence. Two conventions hold everything up: **absence is not falsity** (a cleared status is not "a status that isn't closed"; only `exists`/`is_null` are satisfiable by a missing value), and **unreadability is counted** — zero findings over a clean estate and zero findings over unparseable dates are different claims, and the report says which. The clock is a parameter, serialized as `as_of`: a rule about something being fourteen days old has an answer that depends on when you asked.

**Goal** — a commitment the business holds itself to, declared in `goals.yaml` as three parts: a **metric** (which number), a **target** (what it should be — every target in the file was picked by a person, never derived), and a **strategy** (how to judge). `GET /api/insights/goals` answers with one row per goal — current value, verdict, progress — and a summary. The verdict vocabulary is three-valued on purpose: **met**, **missed**, and **unknown**, and unknown is never folded into missed — "we can't tell" is not a failure. A goal refuses to judge what the estate cannot answer, with the reason on its row: the metric doesn't exist, it errored, it spans currencies, it produced no value, or nothing matched over an *empty estate* — while zero matches over a *real* population is a genuine measurement, and a "keep churn under five" goal rightly goes green on it.

**Strategy** — the judgment rule inside a goal. `at_least` and `at_most` compare the current value to the target (met on equality; a zero target reads done-or-not rather than dividing by zero). `increasing` judges the *snapshot series*, not just its endpoints — a dip that recovers higher is a rise, a shed-and-re-add back to the same level is not, and fewer than two points is not a trend but a refusal with a reason. `threshold_band` is for "hold it near" numbers — bad in *both* directions, like average deal size (too low: selling small; suspiciously high: a whale is skewing the mix, or the mid-market stopped closing). It judges met when the value sits inside a band around the target, and its `detail` names which side was breached. Strategies are pure, total functions over values — no clock, no database, and no input makes one raise — returning `(met, progress, detail)`. More strategies (streaks, growth rates) arrive with the goals that consume them.

**Params** — the tuning knobs a strategy exposes, declared per goal in `goals.yaml`. `threshold_band` takes `band_low: 0.8` / `band_high: 1.25`: multipliers of the target, so a 25,000 target reads healthy anywhere in [20,000 … 31,250]. The asymmetry is a human judgment (more tolerance for drifting high than low), which is why they're params rather than code. The band edges are sorted after multiplying — with a negative target the low multiplier yields the *larger* edge, and the unsorted version produced an inverted band where met was unreachable. Omitted params fall back to declared defaults; param *values* are validated at build time (a `band_low: "wide"` refuses the boot with the problem named, instead of booting clean and 500ing the first time someone opens the goals page).

**Transform** — a pure normalizing function (`normalize_domain`, `normalize_money`, …). Transforms refuse rather than guess: a value they can't interpret raises a named reason (`not_a_date`, `not_a_number`) that lands in the report. A closed registry — data never selects arbitrary code.

**Rebuild** (projection) — `POST /api/rebuild`: wipe the entity layer and recompute it from the newest raw event per record, through mappings and transforms. Deterministic (ids are content-derived uuid5s — two rebuilds produce byte-identical rows), locked (a concurrent rebuild gets a 409), and rebuildable at any time because raw events are never lost.

**Build checks** — `problems = checks.run()`: the line that decides whether the estate is allowed to exist. `run()` reads all nine definition files and cross-validates every claim one makes about another — every mapping names a real connector and a real ontology attribute, every transform exists in the registry and lands the type it claims, every metric term is answerable, every identity attribute is normalized, every goal's strategy exists and its param *values* make sense. It returns a list of problems, each a sentence naming the file, the line's subject, and what's wrong; an empty list is the only passing grade. It runs twice over the system's life: at boot (a non-empty list raises `BuildCheckError` and the app refuses to start — the log line `build checks: ok` is the receipt) and before every rebuild, because the YAMLs are live-mounted and editing one then calling `/api/rebuild` is the ordinary workflow — the check catches the typo *before* the entity layer is wiped, not after. Severity is two-tier: an unparseable `mappings`/`ontology`/`transforms` file fails alone (nothing downstream is checkable without it), while a broken `metrics`/`rules`/`goals` file is reported and checking continues, so one bad file yields its own problem rather than a cascade of confusing ones.

**Report** — the rebuild's self-accounting (`GET /api/report`): every refused value bucketed by reason, every cleared field, every mapping line that matched nothing (`dead_paths` — how you notice a provider renamed a field), every failed row. The design rule: nothing is dropped silently.

**Enrichment** — the first of two layers that call a model, and it is opt-in on purpose (`ENRICHMENT_ENABLED` defaults off; switching it on without an `ANTHROPIC_API_KEY` refuses the boot). Everything above this line in the README is deterministic; from here down is where inference lives, behind one module (`app/llm`) and one flag per layer.

A **reading**, declared in `enrichment.yaml`, is one named way of reading one kind of text: `sales_call` says "take every `meeting`'s `transcript` and answer three questions — interest, pain points, timing — each from a closed set of labels." The `entity:`/`input:` pair is the reading's address into the canonical layer, validated at boot (the attr must exist, be a string, and never be merge identity), and the whole spec — label glosses included — hashes into a `vocabulary_sha`, because the glosses are the prompt: changing a word changes what was asked.

A run (`POST /api/enrichment/run`) works through five refusals-first steps: find **candidates** (canonical entities whose survived input text exists and hasn't been read under the current vocabulary — a digest comparison, so re-runs are cheap), **fence** the text (delimited as quoted speech, a forged closing tag defanged, so a transcript that says "ignore your instructions" is data, not instructions), **ask** with a generated schema the API enforces server-side (labels are a closed enum; every finding must carry a `quote`), **verify** each quote against the source text (an unverifiable quote is kept and *counted*, never dropped — it's the reader's way of saying "I may have paraphrased"), and **write** rows stamped with everything that produced them: `input_sha`, `vocabulary_sha`, `model`, `prompt_version`. One bad transcript costs one transcript — a failed parse is counted with its error, and the rest of the paid batch commits.

Three durability rules: the rebuild never touches `enriched_fact` (it's the one table not derivable from `raw_event` — the substrate is rebuilt around it); when resolution merges two entities, their readings move to the survivor; when an entity vanishes entirely, its readings are kept as orphans rather than destroyed. And **coverage is stated, not assumed** (`GET /api/enrichment/coverage`): `eligible`, `read_under_current_vocabulary`, `read_under_a_retired_vocabulary`, and `never_read` are four different claims, so "the model saw 6 of 6" is a number you read, never an impression you form. Every list payload carries `inferred: true` and a disclaimer: these are model readings, not measurements. The reader is `claude-sonnet-5` by default — closed-enum extraction doesn't need a frontier model — at roughly $1.80 per full 200-call run.

**Role** — a briefing audience, and it exists because a file does: `definitions/briefs/ceo.md` *is* the role `ceo`. No registry, no enum — `roles()` is the directory listing, so a tenant adds a role by writing a prompt file and removes one by deleting it. Each file is that role's editable half of the prompt: what this reader cares about, in what order, at what length ("under 250 words", "money in full figures"). The other half — the SAFETY preamble saying fenced data is material never instruction, never compute, call a defect a defect — lives in code, because *what the role wants to hear* is a tenant decision and *what the model may never do* is not.

**Briefing** (coaching, `COACHING_ENABLED`) — a model narrating the estate's numbers to one role: metrics, goals, and findings walk into a fenced prompt, and ~250 words of prose walk out (`POST /api/coaching/{role}`; the newest success serves at `GET`). It is the system's first *unassertable* artifact — enrichment's labels are server-enforced enums with machine-checked quotes, but no test can assert a paragraph — so all the discipline moved to the input side: the context block is a pure function (no clock, no database) rendered under hard rules — a defective number becomes `UNAVAILABLE` rather than being narrated (a measurement defect must never read as a business result), zero entities reads "measures nothing rather than measuring zero", an inferred metric is marked `ESTIMATE` wherever it appears, and a goal's progress tail says *what its percentage counts* (an `at_most` goal missed by double says "over the ceiling", never "50% of target"). Every generation is stored with full lineage — failures included, because a failed briefing that leaves no row is indistinguishable from one nobody asked for — and the rebuild never touches the table: narrating the same numbers twice does not give the same paragraph, so a briefing is not derivable from `raw_event`.

**prompts_sha** — one digest over every prompt file, stamped on each stored briefing beside `input_sha` (the exact estate block read) and the model. Together they finish the provenance sentence a briefing owes its reader: *these numbers, worded this way, by this model.* Rewording a prompt changes the sha, so an old briefing honestly reads as the product of retired wording rather than a change in the business — the same move as enrichment's `vocabulary_sha`, because in both layers the prose *is* part of the instrument, and an instrument that changed silently would forge its own history.

**Search** (`GET /api/search`, ⌘K in the console, `/search`) — one search over everything stored, with three legs that share one endpoint. *Words*: at every rebuild the engine writes one row per fact into `search_document` — every member's facts, not only the survivorship winners, so a merged person is found by whichever name or email either source knows; the anchor key; enrichment readings with their verified quotes; every briefing; and the latest payload of every raw event — indexed with Postgres `tsvector` under the `simple` configuration (no stemming, so a prefix matches mid-word: `pricin` finds pricing) and weighted so a name outranks a transcript. Emails and domains are also stored as their parts, so `acme` finds `hello@acme.io`. When the word query finds nothing, a trigram pass over names and labels answers instead (`carlso` finds Carlos). A prefix like `person:wayne` sets the kind filter. Every hit carries evidence — the attribute that matched (`status=past_due`) or the passage with the matching words marked — and opens the thing itself: the entity with its row selected, the metric with its series, the briefing in the journal, the raw event in the Raw tab. *Meaning* (`EMBEDDINGS_ENABLED`, `OPENAI_API_KEY`): transcripts are split into chunks at rebuild and embedded by a separate capped run (`POST /api/search/embed`, also after a rebuild) into `search_chunk` with `pgvector`; vectors are keyed on the chunk's hash and model, so a rebuild re-embeds only what changed, and word search keeps working while vectors are missing. *Both* (`mode=both`): reciprocal rank fusion of the two legs, and, with `RERANK_ENABLED` and a ZeroEntropy key, Zerank 2 over the top twenty, falling back to fusion order on any error. The index is exactly as fresh as the last rebuild. Dates and numbers are not indexed; nothing in a raw payload that never became a fact is reachable except through the raw hit itself. Definitions are indexed with their glossary, so a business word reaches the reviewed definition: `revenue` finds the `mrr` metric, `clients` finds the `company` type.

**MCP** (`/mcp`) — the estate as a tool server for any agent on the machine, over the Model Context Protocol (Streamable HTTP). It is read-only and calls no model itself. It serves the conversation's seven tools (`get_metrics`, `slice_metric`, `get_goals`, `get_findings`, `entity_counts`, `find_entities`, `get_entity`) built from the same specs and handlers the ask agent uses, so an agent asking for MRR gets the reviewed number with its receipts rather than a guess over raw tables; the nine definition files as `definitions://<name>` resources, so an agent can read what a metric means before asking for it; and each role brief as a `briefing_<role>` prompt. Every call is written to `mcp_call` (kind, name, arguments, ok, duration, error). `GET /api/mcp` lists what is served; the console's Config → MCP tab shows it with the endpoint and a client config to copy. There is no authentication on `/mcp` or `/api` yet, so it is for localhost only until the OAuth item in `TODO.md` lands.

## Running

```
./test.sh unit    # ruff + full suite, 100% line+branch coverage enforced
./test.sh e2e     # against the live mock estate
./format.sh       # apply lint fixes and formatting
```

The stack is Docker Compose (`app/docker-compose.yml`): postgres :5442, mock :8192, backend :8092. `test.sh` starts it as needed.

Connect an MCP client to the running stack: `claude mcp add --transport http os http://localhost:3092/mcp` for Claude Code, or for Claude Desktop and Cursor:

```json
{ "mcpServers": { "os": { "type": "http", "url": "http://localhost:3092/mcp" } } }
```

Then ask the client for the goals, or for a company by name; the answers come from the tools above and each call shows up in `mcp_call`.

Search the estate from the console: press ⌘K (Ctrl+K on Linux and Windows) on any page, or open Search in the nav (`/search`). Type any word — a name, an email, an id, a status, a word from a transcript or a briefing — and a prefix narrows the kind: `person:wayne`, `briefing:churn`, `raw:sub_000008`. Opening a hit lands on the thing itself with its row selected. From the API:

```
curl 'localhost:8092/api/search?q=past_due'
curl 'localhost:8092/api/search?q=wayne&kind=meeting&limit=5'
```

Each answer carries `total`, `by_kind` and `results` of `kind`, `id`, `label`, `evidence`. The index is refilled at every rebuild, so a search is exactly as fresh as the projection.

Meaning search is opt-in, like every layer that calls a model: set `EMBEDDINGS_ENABLED=true` and `OPENAI_API_KEY` in `app/.env`, restart the backend, then `curl -X POST localhost:8092/api/search/embed` once (it also runs after every rebuild from then on). Query with `mode=meaning` or `mode=both`; the Search page grows a `words · meaning · both` toggle. Reranking on top of `mode=both` needs `RERANK_ENABLED=true` and `ZEROENTROPY_API_KEY`. Startup refuses a flag whose key is missing.

A dev database created before the search PR predates the `pgvector` image: `docker compose -p os -f app/docker-compose.yml down -v`, bring the stack up, sync, rebuild, and re-seed with `python -m tools.seed_demo` inside the backend container.

## Configuration

Everything is read from the environment, and `app/.env` (copied from `app/.env.example`) is loaded first; every knob has a default, so an empty file runs. The three API keys are never settings — the Anthropic and OpenAI clients read theirs from the environment, the ZeroEntropy client reads its own — and startup refuses to run a flag whose key is missing.

| Variable | Default | What it does |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://os:os@localhost:5442/os` | Postgres connection; compose sets it to the `postgres` service |
| `MOCK_BASE_URL` | `http://localhost:8192` | Where the vendored mock providers answer; compose sets `http://mock:8100` |
| `SYNC_RUN_RETENTION_DAYS` | `30` | Sync runs older than this are pruned |
| `ENGINE_RUN_RETENTION` | `200` | Rebuild receipts kept |
| `CONNECTOR_MAX_PAGES` | `500` | Pages a connector pulls per object type before stopping |
| `CONNECTOR_MAX_BYTES` | `52428800` | Payload bytes a connector accepts per pull (50 MiB) |
| `ER_BUCKET_CAP` | `50` | Records per identity bucket before entity resolution refuses to merge it |
| `ER_ONE_RECORD_PER_SOURCE` | `true` | A canonical entity holds at most one record per source |
| `ENRICHMENT_ENABLED` | `false` | Read transcripts into structured facts; needs `ANTHROPIC_API_KEY` |
| `ENRICHMENT_MODEL` | `claude-sonnet-5` | Model for enrichment |
| `ENRICHMENT_MAX_TOKENS` | `8000` | Output cap per enrichment call |
| `ENRICHMENT_MAX_CALLS_PER_RUN` | `200` | Model calls per enrichment run |
| `ENRICHMENT_CONCURRENCY` | `4` | Enrichment calls in flight at once |
| `COACHING_ENABLED` | `false` | Generate role briefings; needs `ANTHROPIC_API_KEY` |
| `COACHING_MODEL` | `claude-sonnet-5` | Model for briefings |
| `COACHING_MAX_TOKENS` | `8000` | Output cap per briefing |
| `CONVERSATION_ENABLED` | `false` | The ask agent; needs `ANTHROPIC_API_KEY` |
| `CONVERSATION_MODEL` | `claude-sonnet-5` | Model for the ask agent |
| `CONVERSATION_MAX_TOKENS` | `8000` | Output cap per turn |
| `CONVERSATION_MAX_TURNS` | `8` | Tool-call rounds per question |
| `CONVERSATION_MAX_TOOL_RESULT_CHARS` | `12000` | A tool result is truncated beyond this |
| `CONVERSATION_MAX_HISTORY_TURNS` | `12` | Earlier turns replayed to the model |
| `CONVERSATION_MAX_TURN_CHARS` | `4000` | A stored turn is truncated beyond this |
| `EMBEDDINGS_ENABLED` | `false` | Meaning search over transcript chunks; needs `OPENAI_API_KEY` |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI embedding model |
| `EMBEDDING_DIMS` | `1536` | Vector width; must match the `search_chunk` column |
| `EMBEDDING_BATCH` | `100` | Chunks per embedding request |
| `EMBEDDINGS_MAX_CALLS_PER_RUN` | `200` | Embedding requests per run |
| `RERANK_ENABLED` | `false` | Zerank over hybrid results; needs `ZEROENTROPY_API_KEY` |
| `RERANK_MODEL` | `zerank-2` | ZeroEntropy reranker model |
| `RERANK_TOP` | `20` | Results sent to the reranker |
| `SEARCH_CHUNK_CHARS` | `1200` | Target size of a transcript chunk |

Keys, set only in the environment or `app/.env`:

| Variable | Needed by |
|---|---|
| `ANTHROPIC_API_KEY` | `ENRICHMENT_ENABLED`, `COACHING_ENABLED`, `CONVERSATION_ENABLED` |
| `OPENAI_API_KEY` | `EMBEDDINGS_ENABLED` |
| `ZEROENTROPY_API_KEY` | `RERANK_ENABLED` |

The compose files add the wiring, not knobs: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` (all `os`) on the database, `BACKEND_URL` on the frontend dev server, and `docker-compose.snap.yml` pins every model flag off for the snapshot stack.

## Layout

- `ROADMAP.md` — the feature-slice plan to v11 parity, checkbox-tracked
- `definitions/` — the definition files (`ontology.yaml` through `derived.yaml`) and `briefs/`, the role prompt files
- `app/backend/` — FastAPI backend; tests in `app/backend/tests/`
- `app/backend/app/sources/` — one package per source: connector plus extract hook
- `app/backend/app/engine/search.py` — the search index (`search_document`, `search_chunk`) refilled at rebuild, the word, trigram and meaning legs, fusion and reranking, served by `api/search_api.py`
- `app/backend/app/mcp.py` — the read-only MCP server at `/mcp` (Streamable HTTP): the conversation's seven tools, the definition files as `definitions://` resources, the role briefs as `briefing_<role>` prompts, every call logged to `mcp_call`; localhost only until auth exists
- `mock/` — vendored mock providers (verbatim; exempt from repo style rules)
