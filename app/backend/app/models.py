import uuid

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Identity,
    Index,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class RawEvent(Base):
    __tablename__ = "raw_event"

    # Row identity, random UUID: 6f1c…, 9b2d…
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Monotonic ingest counter: 1, 2, 3 — insert order
    seq = Column(BigInteger, Identity(), unique=True, nullable=False)
    # Originating system: stripe, hubspot, zoom
    source = Column(String(64), nullable=False)
    # Object kind in source: customers, deals, meetings
    object_type = Column(String(64), nullable=False)
    # Object id in source: cus_000001, deal_88, mtg_20260830
    source_id = Column(String(256), nullable=False)
    # Verbatim source JSON: {"id": "cus_000001", ...}
    raw_payload = Column(JSONB, nullable=False)
    # SHA-256 hex of payload: "a3f9…", "0c7a…"
    payload_sha = Column(String(64), nullable=False)
    # Receipt timestamp: server now(), 2026-08-30T12:00:00Z
    ingested_at = Column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

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
