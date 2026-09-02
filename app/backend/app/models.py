import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class RawEvent(Base):
    __tablename__ = "raw_event"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)  # row identity, random UUID: 6f1c…, 9b2d…
    seq = Column(BigInteger, Identity(), unique=True, nullable=False)  # monotonic ingest counter: 1, 2, 3
    source = Column(String(64), nullable=False)  # originating system: stripe, hubspot, zoom
    object_type = Column(String(64), nullable=False)  # object kind in source: customers, deals, meetings
    source_id = Column(String(256), nullable=False)  # object id in source: cus_000001, deal_88, mtg_20260830
    raw_payload = Column(JSONB, nullable=False)  # verbatim source JSON: {"id": "cus_000001", ...}
    payload_sha = Column(String(64), nullable=False)  # SHA-256 hex of payload: "a3f9…", "0c7a…"
    ingested_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))  # receipt timestamp: server now(), 2026-08-30T12:00:00Z

    __table_args__ = (
        Index(
            "ix_raw_event_identity_seq",
            "source",
            "object_type",
            "source_id",
            text("seq DESC"),
        ),
        Index("ix_raw_event_source_seq", "source", text("seq DESC")),
    )


class Entity(Base):
    __tablename__ = "entity"

    id = Column(UUID(as_uuid=True), primary_key=True)  # uuid5 of anchor key: 9c17…, 0d4e…
    source = Column(String(64), nullable=False)  # originating system: stripe, hubspot, zoom
    entity_type = Column(String(64), nullable=False)  # ontology entity kind: company, person, deal
    source_id = Column(String(256), nullable=False)  # object id in source: cus_000001, deal_88
    object_type = Column(String(64), nullable=False)  # object kind in source: customers, deals, meetings
    first_seq = Column(BigInteger, nullable=False, server_default=text("0"))  # seq of first sighting: 1, 42
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))  # row write timestamp: server now(), 2026-08-30T12:00:00Z

    __table_args__ = (Index("ix_entity_type", "entity_type"),)


class EntityFact(Base):
    __tablename__ = "entity_fact"

    id = Column(UUID(as_uuid=True), primary_key=True)  # uuid5 of anchor+attr: 6f1c…, 9b2d…
    entity_id = Column(UUID(as_uuid=True), ForeignKey("entity.id"), nullable=False)  # owning entity row: 9c17…, 0d4e…
    attr = Column(String(128), nullable=False)  # ontology attribute name: domain, amount, industry
    value = Column(Text)  # normalized value, NULL when cleared: "acme.io", "89.0", null
    is_null = Column(Boolean, nullable=False, server_default=text("false"))  # observed as cleared: true, false
    raw_event_id = Column(UUID(as_uuid=True), ForeignKey("raw_event.id"))  # asserting raw event: 6f1c…, null
    observed_at = Column(DateTime(timezone=True), nullable=False)  # provider modified-at or ingestion: 2026-07-01T10:00:00Z


class EntityCanonical(Base):
    __tablename__ = "entity_canonical"

    canonical_id = Column(UUID(as_uuid=True), primary_key=True)  # uuid5 of anchor key: 9c17…, 0d4e…
    entity_type = Column(String(64), nullable=False)  # ontology entity kind: company, person, deal
    anchor_key = Column(String(512), nullable=False)  # first member's key: stripe|company|cus_000001
    minted_seq = Column(BigInteger, nullable=False)  # mint order from raw seq: 1, 42
    member_count = Column(Integer, nullable=False, server_default=text("0"))  # members in this cluster: 1, 2, 3
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))  # row write timestamp: server now(), 2026-08-30T12:00:00Z

    __table_args__ = (Index("ix_canonical_type", "entity_type"),)


class CanonicalMember(Base):
    __tablename__ = "canonical_member"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)  # uuid5 of member entity: 6f1c…, 9b2d…
    canonical_id = Column(UUID(as_uuid=True), ForeignKey("entity_canonical.canonical_id"), nullable=False)  # owning cluster: 9c17…, 0d4e…
    entity_id = Column(UUID(as_uuid=True), ForeignKey("entity.id"), nullable=False)  # member entity row: 9c17…, 0d4e…
    evidence = Column(String(256), nullable=False, server_default=text("'singleton'"))  # why it joined: domain=acme.io, singleton

    __table_args__ = (Index("ix_member_canonical", "canonical_id"),)


class CanonicalAlias(Base):
    __tablename__ = "canonical_alias"

    alias_id = Column(UUID(as_uuid=True), primary_key=True)  # id no longer minted: 9c17…, 0d4e…
    canonical_id = Column(UUID(as_uuid=True), nullable=False)  # where it points, may be retired: 9c17…, itself
    reason = Column(String(32), nullable=False)  # why it retired: merged, retired
    recorded_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))  # row write timestamp: server now(), 2026-08-30T12:00:00Z

    __table_args__ = (Index("ix_alias_canonical", "canonical_id"),)


class FactCurrent(Base):
    __tablename__ = "fact_current"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)  # uuid5 of cluster+attr: 6f1c…, 9b2d…
    canonical_id = Column(UUID(as_uuid=True), ForeignKey("entity_canonical.canonical_id"), nullable=False)  # owning cluster: 9c17…, 0d4e…
    entity_type = Column(String(64), nullable=False)  # ontology entity kind: company, person, deal
    attr = Column(String(128), nullable=False)  # ontology attribute name: domain, mrr, industry
    value = Column(Text, nullable=False)  # winning value: "acme.io", "49.0"
    value_num = Column(Float)  # numeric form when number: 49.0, null
    entity_id = Column(UUID(as_uuid=True))  # member that won: 9c17…, null
    raw_event_id = Column(UUID(as_uuid=True))  # payload that won: 6f1c…, null
    observed_at = Column(DateTime(timezone=True), nullable=False)  # winning observation time: 2026-07-01T10:00:00Z
    disagreements = Column(Integer, nullable=False, server_default=text("0"))  # other values asserted: 0, 1, 2

    __table_args__ = (
        CheckConstraint(
            "value_num IS NULL OR (value_num <> 'NaN'::float8 "
            "AND value_num > '-Infinity'::float8 AND value_num < 'Infinity'::float8)",
            name="fact_current_num_finite"),
        Index("ix_fact_current_type_attr", "entity_type", "attr"),
    )


class CanonicalLink(Base):
    __tablename__ = "canonical_link"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)  # uuid5 of edge triple: 6f1c…, 9b2d…
    from_canonical = Column(UUID(as_uuid=True), ForeignKey("entity_canonical.canonical_id"), nullable=False)  # subject cluster: 9c17…, 0d4e…
    rel = Column(String(64), nullable=False)  # declared relationship: belongs_to, parent_of
    to_canonical = Column(UUID(as_uuid=True), ForeignKey("entity_canonical.canonical_id"), nullable=False)  # object cluster: 9c17…, 0d4e…
    grounding = Column(String(128), nullable=False)  # what held the edge: via:customer_ref, match:email

    __table_args__ = (
        Index("ix_link_rel", "rel"),
        Index("ix_link_to_rel", "to_canonical", "rel"),
    )


class EngineRun(Base):
    __tablename__ = "engine_run"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)  # row identity, random UUID: 6f1c…, 9b2d…
    seq = Column(BigInteger, Identity(), unique=True, nullable=False)  # monotonic run counter: 1, 2, 3
    ok = Column(Boolean, nullable=False, default=False)  # rebuild succeeded: true, false
    raw_events_read = Column(Integer, nullable=False, server_default=text("0"))  # raw rows projected: 0, 42
    entities_written = Column(Integer, nullable=False, server_default=text("0"))  # entity rows written: 0, 42
    facts_written = Column(Integer, nullable=False, server_default=text("0"))  # fact rows written: 0, 124
    canonical_written = Column(Integer, nullable=False, server_default=text("0"))  # canonical rows written: 0, 52
    links_written = Column(Integer, nullable=False, server_default=text("0"))  # link rows written: 0, 10
    report = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # full sync report: {"totals": {...}}
    duration_ms = Column(Integer, nullable=False, server_default=text("0"))  # rebuild wall time: 5, 1200
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))  # run timestamp: server now(), 2026-08-30T12:00:00Z


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshot"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)  # row identity, random UUID: 6f1c…, 9b2d…
    metric = Column(String(128), nullable=False)  # metric definition name: mrr, deal_count
    value = Column(Float)  # null means no reading: 17147.0, null
    entities = Column(Integer, nullable=False, server_default=text("0"))  # entities measured over: 0, 42
    recorded_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))  # snapshot timestamp: server now(), 2026-08-30T12:00:00Z

    __table_args__ = (
        CheckConstraint(
            "value IS NULL OR (value <> 'NaN'::float8 "
            "AND value > '-Infinity'::float8 AND value < 'Infinity'::float8)",
            name="snapshot_finite"),
        Index("ix_snapshot_metric_time", "metric", text("recorded_at DESC")),
    )


class EnrichedFact(Base):
    __tablename__ = "enriched_fact"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)  # row identity, random UUID: 6f1c…, 9b2d…
    canonical_id = Column(UUID(as_uuid=True), nullable=False)  # entity read, never cascades: 9c17…, 0d4e…
    entity_type = Column(String(64), nullable=False)  # ontology entity kind: meeting
    reading = Column(String(64), nullable=False)  # reading spec name: sales_call, support_call
    attr = Column(String(128), nullable=False)  # question asked: interest, pain_points, timing
    value = Column(String(128), nullable=False)  # label answered: strong, pricing, this_quarter
    quote = Column(Text, nullable=False)  # claimed supporting span: "the pricing is what stalls us"
    quote_verified = Column(Boolean, nullable=False, server_default=text("false"))  # span found in text: true, false
    input_sha = Column(String(64), nullable=False)  # SHA-256 of text read: "a3f9…", "0c7a…"
    vocabulary_sha = Column(String(64), nullable=False)  # spec digest when read: "d41d…", "9e10…"
    model = Column(String(128), nullable=False)  # model that answered: claude-opus-5, claude-test
    prompt_version = Column(String(32), nullable=False)  # prompt wording pin: 2026-08-02.1
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))  # row write timestamp: server now(), 2026-08-30T12:00:00Z

    __table_args__ = (
        UniqueConstraint("canonical_id", "reading", "attr", "value", name="enriched_identity"),
        Index("ix_enriched_stale", "reading", "vocabulary_sha", "canonical_id", "input_sha"),
    )


class EnrichmentRun(Base):
    __tablename__ = "enrichment_run"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)  # row identity, random UUID: 6f1c…, 9b2d…
    seq = Column(BigInteger, Identity(), unique=True, nullable=False)  # monotonic run counter: 1, 2, 3
    reading = Column(String(64), nullable=False)  # reading spec name: sales_call, support_call
    vocabulary_sha = Column(String(64), nullable=False)  # spec digest at run: "d41d…", "9e10…"
    model = Column(String(128), nullable=False)  # model configured for run: claude-opus-5
    prompt_version = Column(String(32), nullable=False)  # prompt wording pin: 2026-08-02.1
    read = Column(Integer, nullable=False, server_default=text("0"))  # entities read and stored: 0, 6
    failed = Column(Integer, nullable=False, server_default=text("0"))  # entities that errored: 0, 1
    truncated_at_cap = Column(Boolean, nullable=False, server_default=text("false"))  # stopped at call cap: true, false
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))  # run timestamp: server now(), 2026-08-30T12:00:00Z

    __table_args__ = (
        Index("ix_enrichment_run_reading", "reading", text("seq DESC")),
    )


class SyncRun(Base):
    __tablename__ = "sync_run"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)  # row identity, random UUID: 6f1c…, 9b2d…
    source = Column(String(64), nullable=False)  # originating system: stripe, hubspot, zoom
    ok = Column(Boolean, nullable=False)  # attempt succeeded: true, false
    rows_written = Column(Integer, nullable=False, server_default=text("0"))  # new raw rows stored: 0, 42
    detail = Column(Text)  # errors, notes, refusals: "RuntimeError: down", null
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))  # attempt start timestamp: app clock, 2026-08-30T12:00:00Z

    __table_args__ = (
        Index("ix_sync_run_source_time", "source", text("started_at DESC")),
    )
