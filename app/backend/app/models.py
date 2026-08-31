import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
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


class EngineRun(Base):
    __tablename__ = "engine_run"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)  # row identity, random UUID: 6f1c…, 9b2d…
    seq = Column(BigInteger, Identity(), unique=True, nullable=False)  # monotonic run counter: 1, 2, 3
    ok = Column(Boolean, nullable=False, default=False)  # rebuild succeeded: true, false
    raw_events_read = Column(Integer, nullable=False, server_default=text("0"))  # raw rows projected: 0, 42
    entities_written = Column(Integer, nullable=False, server_default=text("0"))  # entity rows written: 0, 42
    facts_written = Column(Integer, nullable=False, server_default=text("0"))  # fact rows written: 0, 124
    report = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # full sync report: {"totals": {...}}
    duration_ms = Column(Integer, nullable=False, server_default=text("0"))  # rebuild wall time: 5, 1200
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))  # run timestamp: server now(), 2026-08-30T12:00:00Z


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
