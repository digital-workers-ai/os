import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
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


class PullManifest(Base):
    __tablename__ = "pull_manifest"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)  # row identity, random UUID: 6f1c…, 9b2d…
    seq = Column(BigInteger, Identity(), unique=True, nullable=False)  # monotonic manifest counter: 1, 2, 3
    source = Column(String(64), nullable=False)  # originating system: stripe, hubspot, zoom
    object_type = Column(String(64), nullable=False)  # object kind in source: customers, deals, meetings
    source_ids = Column(JSONB, nullable=False)  # sorted ids one pull saw: ["cus_000001", "cus_000002"]
    observed_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))  # pull completion timestamp: server now(), 2026-08-30T12:00:00Z

    __table_args__ = (
        Index(
            "ix_pull_manifest_identity_seq", "source", "object_type", text("seq DESC")
        ),
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
