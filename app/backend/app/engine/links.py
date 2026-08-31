from dataclasses import dataclass


@dataclass(frozen=True)
class Edge:
    from_canonical: object
    rel: str
    to_canonical: object
    grounding: str


def _fanout_limit(cardinality: str) -> int | None:
    return 1 if cardinality in ("many_to_one", "one_to_one") else None


def build(onto, *, projected: dict, of_record: dict, report) -> list:
    edges: set = set()

    for rel in onto.relationships:
        label = f"{rel.from_type} {rel.rel} {rel.to_type}"
        limit = _fanout_limit(rel.cardinality)
        candidates = 0
        matched = 0
        produced: set = set()

        targets: dict = {}
        for key, entity in projected.items():
            if entity.entity_type == rel.to_type:
                targets[(entity.source, entity.source_id)] = key
        for key, entity in sorted(projected.items()):
            if entity.entity_type != rel.from_type:
                continue
            fact = entity.facts.get(rel.via)
            if fact is None or fact.value is None:
                continue
            candidates += 1
            target_key = targets.get((entity.source, fact.value))
            if target_key is None:
                report.dangling(label)
                continue
            from_canonical = of_record.get(key)
            to_canonical = of_record.get(target_key)
            if from_canonical is None or to_canonical is None:
                report.dangling(label)
                continue
            if from_canonical == to_canonical:
                continue
            matched += 1
            produced.add((from_canonical, rel.rel, to_canonical, f"via:{rel.via}"))

        if limit is not None:
            per_subject: dict = {}
            for from_c, _rel, to_c, _g in produced:
                per_subject.setdefault(from_c, set()).add(to_c)
            for from_c, tos in sorted(per_subject.items(), key=lambda p: str(p[0])):
                if len(tos) > limit:
                    report.quarantine(
                        label,
                        str(from_c),
                        f"resolved to {len(tos)} {rel.to_type} via {rel.via} "
                        f"(expected {limit})",
                    )
                    produced = {e for e in produced if e[0] != from_c}
                    matched -= 1

        report.rate(label, candidates, matched, len(produced))
        edges |= produced

    return [Edge(*e) for e in sorted(edges, key=lambda e: (str(e[0]), e[1], str(e[2])))]
