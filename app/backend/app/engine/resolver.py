import uuid
from dataclasses import dataclass, field

NAMESPACE = uuid.UUID("6b1c9f4e-0a2d-5f83-9c17-0d4e6a8b2f10")

FREE_MAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "yahoo.com",
        "yahoo.co.uk",
        "hotmail.com",
        "outlook.com",
        "live.com",
        "msn.com",
        "aol.com",
        "icloud.com",
        "me.com",
        "mac.com",
        "proton.me",
        "protonmail.com",
        "gmx.com",
        "gmx.de",
        "mail.com",
        "yandex.ru",
        "qq.com",
        "163.com",
        "126.com",
        "naver.com",
        "zoho.com",
        "fastmail.com",
        "hey.com",
        "example.com",
        "example.org",
        "test.com",
        "localhost",
        "email.com",
    }
)

PLACEHOLDER_VALUES = frozenset(
    {
        "n/a",
        "na",
        "none",
        "null",
        "nil",
        "unknown",
        "unspecified",
        "-",
        "--",
        "no",
        "not applicable",
        "tbd",
        "test",
        "noreply",
        "no-reply",
        "no@email.com",
        "test@test.com",
        "noreply@example.com",
        "email@email.com",
    }
)

PLACEHOLDER_PREFIXES = (
    "test@",
    "noreply@",
    "no-reply@",
    "donotreply@",
    "postmaster@",
    "abuse@",
    "invalid@",
)


@dataclass(frozen=True)
class Record:
    source: str
    entity_type: str
    source_id: str
    order: int
    identity: dict = field(default_factory=dict)

    @property
    def key(self) -> tuple:
        return (self.source, self.entity_type, self.source_id)

    @property
    def anchor_key(self) -> str:
        return f"{self.source}|{self.entity_type}|{self.source_id}"


@dataclass
class Cluster:
    canonical_id: uuid.UUID
    entity_type: str
    anchor_key: str
    minted_order: int
    members: dict = field(default_factory=dict)
    sources: set = field(default_factory=set)


def canonical_id_for(anchor_key: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, anchor_key)


def is_blocked(attr: str, value: str) -> str | None:
    text = (value or "").strip().lower()
    if not text:
        return "empty"
    if text in PLACEHOLDER_VALUES:
        return "placeholder"
    if any(text.startswith(p) for p in PLACEHOLDER_PREFIXES):
        return "placeholder_mailbox"
    if text in FREE_MAIL_DOMAINS:
        return "free_mail_domain"
    if "@" in text and text.rsplit("@", 1)[-1] in FREE_MAIL_DOMAINS:
        return None if attr != "domain" else "free_mail_domain"
    return None


def _corroborates(
    left: Record, right: Record, attr: str, identity_attrs
) -> bool | None:
    shared = [
        a
        for a in identity_attrs
        if a != attr
        and str(left.identity.get(a) or "").strip()
        and str(right.identity.get(a) or "").strip()
    ]
    if not shared:
        return None
    return any(
        str(left.identity[a]).strip().lower() == str(right.identity[a]).strip().lower()
        for a in shared
    )


def _namespace_verdicts(ordered, onto, report) -> tuple:
    holders: dict = {}
    for record in ordered:
        for attr in onto.tenant_scoped_attrs(record.entity_type):
            value = record.identity.get(attr)
            if value is None or not str(value).strip():
                continue
            holders.setdefault((record.entity_type, attr, str(value)), {}).setdefault(
                record.source, record
            )

    tally: dict = {}
    witnessed: set = set()
    unwitnessed: dict = {}
    for (entity_type, attr, value), by_source in holders.items():
        identity_attrs = onto.identity_attrs(entity_type)
        sources = sorted(by_source)
        for position, left in enumerate(sources):
            for right in sources[position + 1 :]:
                verdict = _corroborates(
                    by_source[left], by_source[right], attr, identity_attrs
                )
                if verdict is None:
                    report.count(
                        f"identity_unwitnessed/{entity_type}/{attr}/{left}|{right}"
                    )
                    key = (entity_type, attr, frozenset((left, right)))
                    unwitnessed[key] = unwitnessed.get(key, 0) + 1
                    continue
                slot = tally.setdefault(
                    (entity_type, attr, frozenset((left, right))), [0, 0]
                )
                slot[0 if verdict else 1] += 1
                if verdict:
                    witnessed.add((entity_type, attr, value))

    split = set()
    for key, (agreed, disagreed) in sorted(tally.items(), key=str):
        if disagreed <= agreed:
            continue
        entity_type, attr, pair = key
        left, right = sorted(pair)
        split.add(key)
        report.oversize(
            "namespace_not_shared",
            {
                "entity_type": entity_type,
                "attr": attr,
                "sources": [left, right],
                "corroborated": agreed,
                "contradicted": disagreed,
                "detail": (
                    f"{left} and {right} share {disagreed} {attr} value(s) whose "
                    f"records disagree on every other identity attr, against "
                    f"{agreed} that agree — so {attr} is not one namespace across "
                    "these two tools, it is each tool numbering its own rows. "
                    f"{attr} is refused as evidence between them unless a specific "
                    "value is corroborated; other evidence still merges normally"
                ),
            },
        )

    for key, count in sorted(unwitnessed.items(), key=str):
        if key in split or tally.get(key, (0, 0))[0]:
            continue
        entity_type, attr, pair = key
        left, right = sorted(pair)
        split.add(key)
        report.oversize(
            "namespace_unwitnessed",
            {
                "entity_type": entity_type,
                "attr": attr,
                "sources": [left, right],
                "corroborated": 0,
                "contradicted": 0,
                "unwitnessed": count,
                "detail": (
                    f"{left} and {right} share {count} {attr} value(s), and no "
                    f"pair of records holding one agrees on any other identity "
                    f"attr — so nothing says {attr} is one namespace across these "
                    "two tools rather than each numbering its own rows. It is "
                    "refused as evidence between them; a single corroborated "
                    "value anywhere would restore it"
                ),
            },
        )
    return split, witnessed


def resolve(
    records, onto, report, *, bucket_cap: int = 50, one_record_per_source: bool = True
) -> dict:
    ordered = sorted(
        records, key=lambda r: (r.order, r.source, r.entity_type, r.source_id)
    )

    bucket_sources: dict = {}
    for record in ordered:
        for attr in onto.identity_attrs(record.entity_type):
            value = record.identity.get(attr)
            if value is None or is_blocked(attr, str(value)):
                continue
            bucket_sources.setdefault(
                (record.entity_type, attr, str(value)), []
            ).append(record.source)

    quarantined_buckets = set()
    for bucket, sources in bucket_sources.items():
        entity_type, attr, value = bucket
        if len(sources) > len(set(sources)):
            quarantined_buckets.add(bucket)
            duplicated = sorted({s for s in sources if sources.count(s) > 1})
            report.oversize(
                "shared_across_records",
                {
                    "entity_type": entity_type,
                    "attr": attr,
                    "value": value[:80],
                    "records": len(sources),
                    "sources": len(set(sources)),
                    "detail": (
                        f"{attr}={value[:40]!r} appears on "
                        f"{len(sources)} records from only {len(set(sources))} "
                        f"source(s) — {duplicated} holds it more than once, so "
                        "it identifies a function or a group, not one thing"
                    ),
                },
            )
        elif len(sources) > bucket_cap:
            quarantined_buckets.add(bucket)
            report.oversize(
                "identity_bucket",
                {
                    "entity_type": entity_type,
                    "attr": attr,
                    "value": value[:80],
                    "records": len(sources),
                    "cap": bucket_cap,
                    "detail": (
                        f"{len(sources)} records share {attr}="
                        f"{value[:40]!r} — a value that many things share is "
                        "a placeholder, not an identifier; the whole bucket "
                        "is quarantined rather than merged"
                    ),
                },
            )

    namespace_split, namespace_witnessed = _namespace_verdicts(ordered, onto, report)

    clusters: list = []
    index: dict = {}
    of_record: dict = {}
    merged_into: dict = {}

    def refuse_source_bound(record, canonical, detail: str) -> None:
        report.oversize(
            "one_record_per_source",
            {
                "entity_type": record.entity_type,
                "record": record.anchor_key,
                "canonical": str(canonical),
                "detail": detail,
            },
        )

    def mint(record, evidence: str) -> int:
        cluster = Cluster(
            canonical_id=canonical_id_for(record.anchor_key),
            entity_type=record.entity_type,
            anchor_key=record.anchor_key,
            minted_order=record.order,
        )
        cluster.members[record.key] = evidence
        cluster.sources.add(record.source)
        clusters.append(cluster)
        of_record[record.key] = len(clusters) - 1
        return len(clusters) - 1

    def resolve_index(i: int) -> int:
        while i in merged_into:
            i = merged_into[i]
        return i

    for record in ordered:
        identity_attrs = onto.identity_attrs(record.entity_type)
        evidence_keys: list = []
        if identity_attrs:
            usable = 0
            for attr in identity_attrs:
                value = record.identity.get(attr)
                if value is None or not str(value).strip():
                    continue
                reason = is_blocked(attr, str(value))
                if reason:
                    report.count(
                        f"identity_blocked/{record.entity_type}/{attr}/{reason}"
                    )
                    continue
                usable += 1
                bucket = (record.entity_type, attr, str(value))
                if bucket in quarantined_buckets:
                    continue
                evidence_keys.append((attr, str(value)))
            if usable == 0:
                report.no_identity(record.entity_type, record.source)

        hits: list = []
        matched_by: dict = {}
        for attr, value in evidence_keys:
            found = index.get((record.entity_type, attr, value))
            if found is None:
                continue
            found = resolve_index(found)
            candidate = clusters[found]
            blocked = [
                s
                for s in candidate.sources
                if (record.entity_type, attr, frozenset((record.source, s)))
                in namespace_split
            ]
            if blocked and (record.entity_type, attr, value) in namespace_witnessed:
                report.count(f"namespace_value_witnessed/{record.entity_type}/{attr}")
                blocked = []
            if blocked:
                report.oversize(
                    "namespace_not_shared_merge",
                    {
                        "entity_type": record.entity_type,
                        "record": record.anchor_key,
                        "attr": attr,
                        "canonical": str(candidate.canonical_id),
                        "sources": sorted(blocked),
                        "detail": (
                            f"{record.anchor_key} matches this cluster on {attr}="
                            f"{value!r}, but {attr} is not one namespace between "
                            f"{record.source} and {sorted(blocked)} — the merge is "
                            "refused on this evidence. Before guard 5 this merged "
                            "two strangers and reported nothing"
                        ),
                    },
                )
                continue
            if found not in hits:
                hits.append(found)
            matched_by.setdefault(found, (attr, value))
        hits.sort()

        if not hits:
            position = mint(
                record,
                f"{evidence_keys[0][0]}={evidence_keys[0][1]}"
                if evidence_keys
                else "singleton",
            )
            for attr, value in evidence_keys:
                index.setdefault((record.entity_type, attr, value), position)
            continue

        survivor = hits[0]
        target = clusters[survivor]

        if one_record_per_source and record.source in target.sources:
            refuse_source_bound(
                record,
                target.canonical_id,
                f"{record.source} already has a record in this cluster "
                f"({min(target.members)[2]}); a real thing has at most one "
                "record per source, so this merge is refused and the record "
                "stays on its own",
            )
            mint(record, "unmerged_source_bound")
            continue

        matched = matched_by[survivor]
        target.members[record.key] = f"{matched[0]}={matched[1]}"
        target.sources.add(record.source)
        of_record[record.key] = survivor

        for other in hits[1:]:
            loser = clusters[other]
            clash = loser.sources & target.sources
            if one_record_per_source and clash:
                refuse_source_bound(
                    record,
                    target.canonical_id,
                    f"merging {loser.anchor_key} would put two "
                    f"{min(clash)} records in one cluster — refused, the "
                    "clusters stay apart",
                )
                continue
            target.members.update(loser.members)
            target.sources |= loser.sources
            merged_into[other] = survivor

        for attr, value in evidence_keys:
            index.setdefault((record.entity_type, attr, value), survivor)

    return {
        "clusters": [c for i, c in enumerate(clusters) if i not in merged_into],
        "aliases": {
            clusters[i].canonical_id: clusters[resolve_index(i)].canonical_id
            for i in merged_into
        },
        "of_record": {
            key: clusters[resolve_index(i)].canonical_id for key, i in of_record.items()
        },
    }


# When a person has confirmed that two records are the same, this joins
# their two groups. It runs after the automatic merging, so it never
# changes what the machine decided; it only glues two of its results
# together. The older group keeps its id, so the same confirmation lands
# the same way on every rebuild and nothing has to be stored except the
# decision itself.
def union(resolution: dict, pairs) -> dict:
    live = {c.canonical_id: c for c in resolution["clusters"]}
    of_record, aliases = resolution["of_record"], resolution["aliases"]
    for seq, left_anchor, right_anchor in pairs:
        keys = [tuple(anchor.split("|", 2)) for anchor in (left_anchor, right_anchor)]
        # the cluster each record belongs to right now
        sides = [live.get(of_record.get(key)) for key in keys]
        # either record gone, or both already in one cluster
        if None in sides or sides[0] is sides[1]:
            continue
        # survivor: minted earliest, same rule as the resolver, so the anchor and
        # id stay stable
        survivor, loser = sorted(sides, key=lambda c: (c.minted_order, c.anchor_key))
        joined = keys[1] if sides[1] is loser else keys[0]
        # move the loser's members in; the joined record's evidence says which
        # candidate a human confirmed
        survivor.members.update(loser.members)
        survivor.members[joined] = f"human={seq}"
        # fold in the loser's sources, drop the loser
        survivor.sources |= loser.sources
        del live[loser.canonical_id]
        # every alias that pointed at the loser now points at the survivor, and
        # the loser's own id becomes an alias
        aliases.update(
            {
                alias: survivor.canonical_id
                for alias, target in aliases.items()
                if target == loser.canonical_id
            }
        )
        aliases[loser.canonical_id] = survivor.canonical_id
        # repoint the loser's records
        of_record.update(dict.fromkeys(loser.members, survivor.canonical_id))
    # only the clusters still alive
    resolution["clusters"] = [
        c for c in resolution["clusters"] if c.canonical_id in live
    ]
    return resolution
