import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Computed,
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
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase

from app.config import settings
from app.search_vocab import LABEL_CHARS, TEXT_SEARCH_CONFIG, Weight


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
    inferred = Column(Boolean, nullable=False, server_default=text("false"))  # value came from model: true, false
    vocabulary_sha = Column(String(64))  # vocabulary digest, inferred only: "d41d…", null
    produced_by = Column(String(512))  # model@prompt, comma-joined: "claude-sonnet-5@2026-08-02.1", null
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
    model = Column(String(128), nullable=False)  # model that answered: claude-sonnet-5, claude-test
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
    model = Column(String(128), nullable=False)  # model configured for run: claude-sonnet-5
    prompt_version = Column(String(32), nullable=False)  # prompt wording pin: 2026-08-02.1
    read = Column(Integer, nullable=False, server_default=text("0"))  # entities read and stored: 0, 6
    failed = Column(Integer, nullable=False, server_default=text("0"))  # entities that errored: 0, 1
    truncated_at_cap = Column(Boolean, nullable=False, server_default=text("false"))  # stopped at call cap: true, false
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))  # run timestamp: server now(), 2026-08-30T12:00:00Z

    __table_args__ = (
        Index("ix_enrichment_run_reading", "reading", text("seq DESC")),
    )


class BriefingRun(Base):
    __tablename__ = "briefing_run"

    seq = Column(BigInteger, Identity(), primary_key=True)  # monotonic briefing counter: 1, 2, 3
    role = Column(String(64), nullable=False)  # briefing audience role: ceo, head_of_sales
    ok = Column(Boolean, nullable=False)  # model call succeeded: true, false
    model = Column(String(128), nullable=False)  # model configured for run: claude-sonnet-5, claude-test
    prompt_version = Column(String(32), nullable=False)  # prompt wording pin: 2026-08-02.1
    prompts_sha = Column(String(64), nullable=False)  # digest of role prompts: "a3f9…", "0c7a…"
    input_sha = Column(String(64), nullable=False)  # SHA-256 of context block: "b2d4…", "9e10…"
    read_manifest = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # what the model saw: {"metrics": {"mrr": 17147.0}}
    briefing = Column(Text)  # narration, null when failed: "Pipeline is up.", null
    error = Column(Text)  # failure detail: "APIError: down", null
    duration_ms = Column(Integer, nullable=False, server_default=text("0"))  # call wall time: 12, 3400
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))  # run timestamp: server now(), 2026-08-30T12:00:00Z

    __table_args__ = (
        Index("ix_briefing_run_role_seq", "role", text("seq DESC")),
    )


class ConversationThread(Base):
    __tablename__ = "conversation_thread"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)  # row identity, random UUID: 6f1c…, 9b2d…
    seq = Column(BigInteger, Identity(), unique=True, nullable=False)  # monotonic thread counter: 1, 2, 3
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))  # thread creation timestamp: server now(), 2026-08-30T12:00:00Z
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))  # last turn timestamp: server now(), 2026-08-30T12:05:00Z

    __table_args__ = (
        Index("ix_conversation_thread_seq", text("seq DESC")),
    )


class ConversationTurn(Base):
    __tablename__ = "conversation_turn"

    seq = Column(BigInteger, Identity(), primary_key=True)  # monotonic turn counter: 1, 2, 3
    thread_id = Column(UUID(as_uuid=True), ForeignKey("conversation_thread.id", ondelete="CASCADE"), nullable=False)  # owning thread: 9c17…, 0d4e…
    question = Column(Text, nullable=False)  # what the user asked: "what is mrr?"
    answer = Column(Text, nullable=False)  # what the model answered: "MRR is 17,147."
    receipts = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # tool calls behind answer: [{"tool": "get_metrics", "input": {}}]
    model = Column(String(128), nullable=False)  # model that answered: claude-sonnet-5, claude-test
    prompt_version = Column(String(32), nullable=False)  # prompt wording pin: 2026-08-02.1
    loop_turns = Column(Integer, nullable=False, server_default=text("0"))  # model calls this turn: 1, 3
    exhausted = Column(Boolean, nullable=False, server_default=text("false"))  # stopped at turn cap: true, false
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))  # row write timestamp: server now(), 2026-08-30T12:00:00Z

    __table_args__ = (
        Index("ix_conversation_turn_thread_seq", "thread_id", text("seq DESC")),
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


class SourceSetting(Base):
    __tablename__ = "source_setting"

    source = Column(String(64), primary_key=True)  # connector key: hubspot, stripe, zendesk
    enabled = Column(Boolean, nullable=False)  # sync allowed: true, false
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))  # last change: server now(), 2026-09-04T12:00:00Z


class McpCall(Base):
    __tablename__ = "mcp_call"

    seq = Column(BigInteger, Identity(), primary_key=True)  # monotonic call counter: 1, 2, 3
    kind = Column(String(16), nullable=False)  # what was requested: tool, resource, prompt
    name = Column(String(128), nullable=False)  # tool, uri or prompt: get_metrics, definitions://metrics, briefing_ceo
    arguments = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # arguments as given: {"name": "mrr"}, {}
    ok = Column(Boolean, nullable=False)  # call succeeded: true, false
    duration_ms = Column(Integer, nullable=False, server_default=text("0"))  # call wall time: 12, 3400
    error = Column(Text)  # failure detail: "Error calling tool 'get_goals': down", null
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))  # call timestamp: server now(), 2026-09-04T12:00:00Z


class MergeCandidate(Base):
    __tablename__ = "merge_candidate"

    seq = Column(BigInteger, Identity(), primary_key=True)  # monotonic candidate counter: 1, 2, 3
    entity_type = Column(String(64), nullable=False)  # ontology entity kind: person
    left_anchor = Column(String(512), nullable=False)  # lower record key of pair: intercom|person|con_1
    right_anchor = Column(String(512), nullable=False)  # higher record key of pair: zendesk|person|u_1
    score = Column(Float, nullable=False)  # name similarity: 0.8, 0.93, 1.0
    status = Column(String(16), nullable=False, server_default=text("'pending'"))  # review state: pending, confirmed, rejected
    evidence_holds = Column(Boolean, nullable=False, server_default=text("true"))  # corroboration still agrees: true, false
    decided_at = Column(DateTime(timezone=True))  # when reviewed, null pending: 2026-09-04T12:00:00Z, null
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))  # row write timestamp: server now(), 2026-08-30T12:00:00Z

    __table_args__ = (
        UniqueConstraint("entity_type", "left_anchor", "right_anchor", name="merge_candidate_pair"),
    )


class MergeCandidateEvidence(Base):
    __tablename__ = "merge_candidate_evidence"

    seq = Column(BigInteger, Identity(), primary_key=True)  # monotonic evidence counter: 1, 2, 3
    candidate_seq = Column(BigInteger, ForeignKey("merge_candidate.seq", ondelete="CASCADE"), nullable=False)  # owning candidate: 1, 42
    attr = Column(String(64), nullable=False)  # what agreed: name, phone, email_domain
    left_value = Column(Text, nullable=False)  # left record's value: "C Chinchilla", "+14155550101"
    right_value = Column(Text, nullable=False)  # right record's value: "Carlos Ch", "+14155550101"


class SearchDocument(Base):
    __tablename__ = "search_document"

    id = Column(UUID(as_uuid=True), primary_key=True)  # uuid5 of kind|ref_id|attr|ordinal: 6f1c…, 9b2d…
    kind = Column(String(64), nullable=False)  # entity type or document kind: person, briefing, raw
    ref_id = Column(String(160), nullable=False)  # what the hit opens: 9c17…, ceo/4, 6f1c…
    label = Column(String(LABEL_CHARS), nullable=False)  # hit label: "Wayne Enterprises", "CEO · 4 Sep 2026"
    attr = Column(String(128), nullable=False)  # source attribute: name, anchor, reading:sales_call, payload
    value = Column(Text, nullable=False)  # display value: "Wayne Enterprises", "interest=strong", "stripe|company|cus_001"
    text = Column(Text, nullable=False)  # the indexed words: "Wayne Enterprises", "hello@acme.io hello acme.io acme"
    weight = Column(String(1), nullable=False)  # rank weight, A strongest: A, B, D
    happened_at = Column(DateTime(timezone=True))  # briefing or meeting time: 2026-09-04T12:00:00Z, null
    tsv = Column(TSVECTOR, Computed(f"setweight(to_tsvector('{TEXT_SEARCH_CONFIG}', text), weight::\"char\")", persisted=True))  # weighted lexemes: 'wayne':1A 'enterprises':2A

    __table_args__ = (
        Index("ix_search_document_tsv", "tsv", postgresql_using="gin"),
        Index(
            "ix_search_document_trgm",
            "text",
            postgresql_using="gin",
            postgresql_ops={"text": "gin_trgm_ops"},
            postgresql_where=f"weight IN ('{Weight.STRONG}', '{Weight.NORMAL}')",
        ),
        Index("ix_search_document_ref", "kind", "ref_id"),
    )


class SearchChunk(Base):
    __tablename__ = "search_chunk"

    id = Column(UUID(as_uuid=True), primary_key=True)  # uuid5 of canonical_id|attr|chunk_index: 6f1c…, 9b2d…
    canonical_id = Column(UUID(as_uuid=True), nullable=False)  # owning canonical entity: 9c17…, 0d4e…
    attr = Column(String(128), nullable=False)  # source attribute: transcript
    chunk_index = Column(Integer, nullable=False)  # position within attribute text: 0, 1, 7
    text = Column(Text, nullable=False)  # chunk words: "Bruce: the pricing is what stalls us"
    sha = Column(String(64), nullable=False)  # SHA-256 hex of text: "a3f9…", "0c7a…"
    model = Column(String(128))  # embedding model, null until embedded: text-embedding-3-small, null
    embedding = Column(Vector(settings.EMBEDDING_DIMS))  # embedding vector, null until embedded: [0.01, -0.2, …], null
    embedded_at = Column(DateTime(timezone=True))  # embedding timestamp: 2026-09-04T12:00:00Z, null

    __table_args__ = (
        UniqueConstraint("canonical_id", "attr", "chunk_index", name="search_chunk_position"),
        Index(
            "ix_search_chunk_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class EmbeddingRun(Base):
    __tablename__ = "embedding_run"

    seq = Column(BigInteger, Identity(), primary_key=True)  # monotonic run counter: 1, 2, 3
    ok = Column(Boolean, nullable=False)  # every batch succeeded: true, false
    model = Column(String(128), nullable=False)  # embedding model configured: text-embedding-3-small
    embedded = Column(Integer, nullable=False, server_default=text("0"))  # chunks embedded this run: 0, 42
    skipped = Column(Integer, nullable=False, server_default=text("0"))  # chunks already current: 0, 300
    failed = Column(Integer, nullable=False, server_default=text("0"))  # chunks whose batch errored: 0, 100
    error = Column(Text)  # first failure detail: "RateLimitError: quota", null
    truncated_at_cap = Column(Boolean, nullable=False, server_default=text("false"))  # stopped at call cap: true, false
    duration_ms = Column(Integer, nullable=False, server_default=text("0"))  # run wall time: 12, 3400
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))  # run timestamp: server now(), 2026-09-04T12:00:00Z
