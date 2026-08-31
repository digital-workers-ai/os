from dataclasses import dataclass, field
from datetime import datetime

from app.engine import extract, mappings, transforms


@dataclass
class ProjectedFact:
    attr: str
    value: str | None
    value_num: float | None
    raw_event_id: object
    observed_at: datetime
    observed_at_source: str
    seq: int


@dataclass
class ProjectedEntity:
    source: str
    entity_type: str
    source_id: str
    object_type: str
    first_seq: int
    facts: dict = field(default_factory=dict)

    @property
    def key(self) -> tuple:
        return (self.source, self.entity_type, self.source_id)

    @property
    def anchor_key(self) -> str:
        return f"{self.source}|{self.entity_type}|{self.source_id}"


def _is_null_observation(value) -> bool:
    if value is None:
        return True
    return isinstance(value, str) and not value.strip()


def _type_ok(kind: str, value) -> bool:
    if kind == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    if kind == "date":
        return isinstance(value, str) and len(value) >= 10 and value[4] == "-"
    return isinstance(value, str)


def observed_at_for(module, object_type: str, payload: dict, ingested_at: datetime):
    declared = getattr(module, "OBSERVED_AT", None) or {}
    path = declared.get(object_type)
    if not path:
        return ingested_at, "ingested"
    raw = mappings.extract_path(payload, tuple(mappings.split_key(path)))
    if mappings.is_missing(raw) or _is_null_observation(raw):
        return ingested_at, "ingested"
    try:
        text = transforms.normalize_date(
            getattr(module, "SOURCE", ""), object_type, raw
        )
    except transforms.TransformError:
        return ingested_at, "ingested"
    return datetime.fromisoformat(text.replace("Z", "+00:00")), "provider"


def project_payload(
    *,
    source: str,
    object_type: str,
    source_id: str,
    payload: dict,
    raw_event_id,
    ingested_at: datetime,
    seq: int,
    first_seq: int | None = None,
    onto,
    line_index: dict,
    transform_map: dict,
    report,
    connector_module=None,
) -> list[ProjectedEntity]:
    lines = line_index.get((source, object_type), [])
    if not lines:
        return []

    try:
        records = extract.reshape(source, object_type, payload)
    except extract.ExtractError as e:
        report.record_skip(source, object_type, f"extract:{e}"[:80])
        return []

    out: list[ProjectedEntity] = []
    for record in records:
        observed_at, observed_kind = observed_at_for(
            connector_module, object_type, payload, ingested_at
        )
        if observed_kind == "ingested":
            report.count(f"observed_at_fallback/{source}")

        by_entity: dict = {}
        for line in lines:
            report.declare_path(line.entity, line.key)
            raw = mappings.extract_path(record, line.path)
            if mappings.is_missing(raw):
                continue
            report.hit_path(line.entity, line.key)

            entity = by_entity.setdefault(line.entity, {})
            if _is_null_observation(raw):
                entity[line.label] = ProjectedFact(
                    attr=line.label,
                    value=None,
                    value_num=None,
                    raw_event_id=raw_event_id,
                    observed_at=observed_at,
                    observed_at_source=observed_kind,
                    seq=seq,
                )
                report.clear(line.label, source)
                continue

            transform_name = transform_map.get(line.label)
            try:
                value = (
                    transforms.apply(transform_name, source, object_type, raw)
                    if transform_name
                    else raw
                )
            except transforms.TransformError as e:
                report.skip(line.label, source, e.reason)
                continue

            kind = onto.attr_type(line.entity, line.label) or "string"
            if not _type_ok(kind, value):
                report.skip(line.label, source, f"not_{kind}")
                continue

            entity[line.label] = ProjectedFact(
                attr=line.label,
                value=str(value),
                value_num=float(value) if kind == "number" else None,
                raw_event_id=raw_event_id,
                observed_at=observed_at,
                observed_at_source=observed_kind,
                seq=seq,
            )

        account_currency = getattr(connector_module, "ACCOUNT_CURRENCY", None)
        if account_currency:
            for entity_type, facts in by_entity.items():
                if not facts:
                    continue
                if onto.attr_type(entity_type, "currency") is None:
                    continue
                try:
                    value = transforms.normalize_currency(
                        source, object_type, account_currency
                    )
                except transforms.TransformError as e:
                    report.skip("currency", source, f"account_level_{e.reason}")
                    continue
                facts["currency"] = ProjectedFact(
                    attr="currency",
                    value=value,
                    value_num=None,
                    raw_event_id=raw_event_id,
                    observed_at=observed_at,
                    observed_at_source=observed_kind,
                    seq=seq,
                )
                report.count(f"account_currency/{source}")

        for entity_type, facts in by_entity.items():
            if not facts:
                report.record_skip(source, object_type, f"no_facts/{entity_type}")
                continue
            out.append(
                ProjectedEntity(
                    source=source,
                    entity_type=entity_type,
                    source_id=source_id,
                    object_type=object_type,
                    first_seq=seq if first_seq is None else first_seq,
                    facts=facts,
                )
            )
    return out


def project_rows(
    rows,
    *,
    onto,
    line_index,
    transform_map,
    report,
    connectors: dict,
    first_seen: dict | None = None,
) -> dict:
    projected: dict = {}
    for row in rows:
        try:
            entities = project_payload(
                source=row.source,
                object_type=row.object_type,
                source_id=row.source_id,
                payload=row.raw_payload,
                raw_event_id=row.id,
                ingested_at=row.ingested_at,
                seq=row.seq,
                first_seq=(first_seen or {}).get(
                    (row.source, row.object_type, row.source_id), row.seq
                ),
                onto=onto,
                line_index=line_index,
                transform_map=transform_map,
                report=report,
                connector_module=connectors.get(row.source),
            )
        except Exception as e:
            report.record_skip(
                row.source,
                row.object_type,
                f"row_failed/{row.source_id}/{type(e).__name__}"[:80],
            )
            continue
        for entity in entities:
            projected[entity.key] = entity
    return projected
