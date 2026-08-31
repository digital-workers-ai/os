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

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seq = Column(BigInteger, Identity(), unique=True, nullable=False)
    source = Column(String(64), nullable=False)
    object_type = Column(String(64), nullable=False)
    source_id = Column(String(256), nullable=False)
    raw_payload = Column(JSONB, nullable=False)
    payload_sha = Column(String(64), nullable=False)
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
