from dataclasses import dataclass


@dataclass
class FoldedFact:
    canonical_id: object
    entity_type: str
    attr: str
    value: str
    value_num: float | None
    source: str
    entity_key: tuple
    raw_event_id: object
    observed_at: object
    disagreements: int


def _rank(fact, entity, onto):
    return (
        fact.observed_at,
        -onto.priority_index(entity.source),
        entity.source,
        entity.source_id,
    )


def fold(clusters, projected: dict, onto, report) -> list:
    folded: list[FoldedFact] = []

    for cluster in clusters:
        by_attr: dict = {}
        for key in cluster.members:
            entity = projected.get(key)
            if entity is None:
                continue
            for attr, fact in entity.facts.items():
                by_attr.setdefault(attr, []).append((fact, entity))

        for attr, observations in sorted(by_attr.items()):
            observations.sort(
                key=lambda pair: _rank(pair[0], pair[1], onto), reverse=True
            )
            winner_fact, winner_entity = observations[0]

            values = {f.value for f, _ in observations if f.value is not None}
            if len(values) > 1:
                report.disagree(cluster.entity_type, attr, len(values) - 1)

            if winner_fact.value is None:
                report.count(f"cleared_canonical/{cluster.entity_type}/{attr}")
                continue

            folded.append(
                FoldedFact(
                    canonical_id=cluster.canonical_id,
                    entity_type=cluster.entity_type,
                    attr=attr,
                    value=winner_fact.value,
                    value_num=winner_fact.value_num,
                    source=winner_entity.source,
                    entity_key=winner_entity.key,
                    raw_event_id=winner_fact.raw_event_id,
                    observed_at=winner_fact.observed_at,
                    disagreements=len(values) - 1,
                )
            )
    return folded
