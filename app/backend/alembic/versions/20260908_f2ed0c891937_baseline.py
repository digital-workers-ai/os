from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f2ed0c891937"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table(
        "briefing_run",
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=32), nullable=False),
        sa.Column("prompts_sha", sa.String(length=64), nullable=False),
        sa.Column("input_sha", sa.String(length=64), nullable=False),
        sa.Column(
            "read_manifest",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("briefing", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "duration_ms", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("seq"),
    )
    op.create_index(
        "ix_briefing_run_role_seq",
        "briefing_run",
        ["role", sa.literal_column("seq DESC")],
        unique=False,
    )
    op.create_table(
        "canonical_alias",
        sa.Column("alias_id", sa.UUID(), nullable=False),
        sa.Column("canonical_id", sa.UUID(), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("alias_id"),
    )
    op.create_index(
        "ix_alias_canonical", "canonical_alias", ["canonical_id"], unique=False
    )
    op.create_table(
        "conversation_thread",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("seq"),
    )
    op.create_index(
        "ix_conversation_thread_seq",
        "conversation_thread",
        [sa.literal_column("seq DESC")],
        unique=False,
    )
    op.create_table(
        "embedding_run",
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column(
            "embedded", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("skipped", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("failed", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "truncated_at_cap",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "duration_ms", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("seq"),
    )
    op.create_table(
        "engine_run",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column(
            "raw_events_read", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "entities_written",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "facts_written", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "canonical_written",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "links_written", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "report",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "duration_ms", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("seq"),
    )
    op.create_table(
        "enriched_fact",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("canonical_id", sa.UUID(), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("reading", sa.String(length=64), nullable=False),
        sa.Column("attr", sa.String(length=128), nullable=False),
        sa.Column("value", sa.String(length=128), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column(
            "quote_verified",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("input_sha", sa.String(length=64), nullable=False),
        sa.Column("vocabulary_sha", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "canonical_id", "reading", "attr", "value", name="enriched_identity"
        ),
    )
    op.create_index(
        "ix_enriched_stale",
        "enriched_fact",
        ["reading", "vocabulary_sha", "canonical_id", "input_sha"],
        unique=False,
    )
    op.create_table(
        "enrichment_run",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("reading", sa.String(length=64), nullable=False),
        sa.Column("vocabulary_sha", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=32), nullable=False),
        sa.Column("read", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("failed", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "truncated_at_cap",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("seq"),
    )
    op.create_index(
        "ix_enrichment_run_reading",
        "enrichment_run",
        ["reading", sa.literal_column("seq DESC")],
        unique=False,
    )
    op.create_table(
        "entity",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=256), nullable=False),
        sa.Column("object_type", sa.String(length=64), nullable=False),
        sa.Column(
            "first_seq", sa.BigInteger(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_entity_type", "entity", ["entity_type"], unique=False)
    op.create_table(
        "entity_canonical",
        sa.Column("canonical_id", sa.UUID(), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("anchor_key", sa.String(length=512), nullable=False),
        sa.Column("minted_seq", sa.BigInteger(), nullable=False),
        sa.Column(
            "member_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("canonical_id"),
    )
    op.create_index(
        "ix_canonical_type", "entity_canonical", ["entity_type"], unique=False
    )
    op.create_table(
        "mcp_call",
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column(
            "arguments",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column(
            "duration_ms", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("seq"),
    )
    op.create_table(
        "merge_candidate",
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("left_anchor", sa.String(length=512), nullable=False),
        sa.Column("right_anchor", sa.String(length=512), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "evidence_holds",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("seq"),
        sa.UniqueConstraint(
            "entity_type", "left_anchor", "right_anchor", name="merge_candidate_pair"
        ),
    )
    op.create_table(
        "metric_snapshot",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("metric", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column(
            "entities", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "inferred", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("vocabulary_sha", sa.String(length=64), nullable=True),
        sa.Column("produced_by", sa.String(length=512), nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "value IS NULL OR (value <> 'NaN'::float8 AND value > '-Infinity'::float8 AND value < 'Infinity'::float8)",
            name="snapshot_finite",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_snapshot_metric_time",
        "metric_snapshot",
        ["metric", sa.literal_column("recorded_at DESC")],
        unique=False,
    )
    op.create_table(
        "raw_event",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("object_type", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=256), nullable=False),
        sa.Column(
            "raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("payload_sha", sa.String(length=64), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("seq"),
    )
    op.create_index(
        "ix_raw_event_identity_seq",
        "raw_event",
        ["source", "object_type", "source_id", sa.literal_column("seq DESC")],
        unique=False,
    )
    op.create_index(
        "ix_raw_event_source_seq",
        "raw_event",
        ["source", sa.literal_column("seq DESC")],
        unique=False,
    )
    op.create_table(
        "search_chunk",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("canonical_id", sa.UUID(), nullable=False),
        sa.Column("attr", sa.String(length=128), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("sha", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(1536), nullable=True),
        sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "canonical_id", "attr", "chunk_index", name="search_chunk_position"
        ),
    )
    op.create_index(
        "ix_search_chunk_embedding",
        "search_chunk",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_table(
        "search_document",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("ref_id", sa.String(length=160), nullable=False),
        sa.Column("label", sa.String(length=512), nullable=False),
        sa.Column("attr", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("weight", sa.String(length=1), nullable=False),
        sa.Column("happened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "tsv",
            postgresql.TSVECTOR(),
            sa.Computed(
                "setweight(to_tsvector('simple', text), weight::\"char\")",
                persisted=True,
            ),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_search_document_ref", "search_document", ["kind", "ref_id"], unique=False
    )
    op.create_index(
        "ix_search_document_trgm",
        "search_document",
        ["text"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"text": "gin_trgm_ops"},
        postgresql_where="weight IN ('A', 'B')",
    )
    op.create_index(
        "ix_search_document_tsv",
        "search_document",
        ["tsv"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_table(
        "source_setting",
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("source"),
    )
    op.create_table(
        "sync_run",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column(
            "rows_written", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sync_run_source_time",
        "sync_run",
        ["source", sa.literal_column("started_at DESC")],
        unique=False,
    )
    op.create_table(
        "canonical_link",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("from_canonical", sa.UUID(), nullable=False),
        sa.Column("rel", sa.String(length=64), nullable=False),
        sa.Column("to_canonical", sa.UUID(), nullable=False),
        sa.Column("grounding", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(
            ["from_canonical"],
            ["entity_canonical.canonical_id"],
        ),
        sa.ForeignKeyConstraint(
            ["to_canonical"],
            ["entity_canonical.canonical_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_link_rel", "canonical_link", ["rel"], unique=False)
    op.create_index(
        "ix_link_to_rel", "canonical_link", ["to_canonical", "rel"], unique=False
    )
    op.create_table(
        "canonical_member",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("canonical_id", sa.UUID(), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column(
            "evidence",
            sa.String(length=256),
            server_default=sa.text("'singleton'"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["canonical_id"],
            ["entity_canonical.canonical_id"],
        ),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["entity.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_member_canonical", "canonical_member", ["canonical_id"], unique=False
    )
    op.create_table(
        "conversation_turn",
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("thread_id", sa.UUID(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column(
            "receipts",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=32), nullable=False),
        sa.Column(
            "loop_turns", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "exhausted", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"], ["conversation_thread.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("seq"),
    )
    op.create_index(
        "ix_conversation_turn_thread_seq",
        "conversation_turn",
        ["thread_id", sa.literal_column("seq DESC")],
        unique=False,
    )
    op.create_table(
        "entity_fact",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("attr", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column(
            "is_null", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("raw_event_id", sa.UUID(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["entity.id"],
        ),
        sa.ForeignKeyConstraint(
            ["raw_event_id"],
            ["raw_event.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "fact_current",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("canonical_id", sa.UUID(), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("attr", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("value_num", sa.Float(), nullable=True),
        sa.Column("entity_id", sa.UUID(), nullable=True),
        sa.Column("raw_event_id", sa.UUID(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "disagreements", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.CheckConstraint(
            "value_num IS NULL OR (value_num <> 'NaN'::float8 AND value_num > '-Infinity'::float8 AND value_num < 'Infinity'::float8)",
            name="fact_current_num_finite",
        ),
        sa.ForeignKeyConstraint(
            ["canonical_id"],
            ["entity_canonical.canonical_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_fact_current_type_attr",
        "fact_current",
        ["entity_type", "attr"],
        unique=False,
    )
    op.create_table(
        "merge_candidate_evidence",
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("candidate_seq", sa.BigInteger(), nullable=False),
        sa.Column("attr", sa.String(length=64), nullable=False),
        sa.Column("left_value", sa.Text(), nullable=False),
        sa.Column("right_value", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_seq"], ["merge_candidate.seq"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("seq"),
    )


def downgrade() -> None:
    op.drop_table("merge_candidate_evidence")
    op.drop_index("ix_fact_current_type_attr", table_name="fact_current")
    op.drop_table("fact_current")
    op.drop_table("entity_fact")
    op.drop_index("ix_conversation_turn_thread_seq", table_name="conversation_turn")
    op.drop_table("conversation_turn")
    op.drop_index("ix_member_canonical", table_name="canonical_member")
    op.drop_table("canonical_member")
    op.drop_index("ix_link_to_rel", table_name="canonical_link")
    op.drop_index("ix_link_rel", table_name="canonical_link")
    op.drop_table("canonical_link")
    op.drop_index("ix_sync_run_source_time", table_name="sync_run")
    op.drop_table("sync_run")
    op.drop_table("source_setting")
    op.drop_index(
        "ix_search_document_tsv", table_name="search_document", postgresql_using="gin"
    )
    op.drop_index(
        "ix_search_document_trgm",
        table_name="search_document",
        postgresql_using="gin",
        postgresql_ops={"text": "gin_trgm_ops"},
        postgresql_where="weight IN ('A', 'B')",
    )
    op.drop_index("ix_search_document_ref", table_name="search_document")
    op.drop_table("search_document")
    op.drop_index(
        "ix_search_chunk_embedding",
        table_name="search_chunk",
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.drop_table("search_chunk")
    op.drop_index("ix_raw_event_source_seq", table_name="raw_event")
    op.drop_index("ix_raw_event_identity_seq", table_name="raw_event")
    op.drop_table("raw_event")
    op.drop_index("ix_snapshot_metric_time", table_name="metric_snapshot")
    op.drop_table("metric_snapshot")
    op.drop_table("merge_candidate")
    op.drop_table("mcp_call")
    op.drop_index("ix_canonical_type", table_name="entity_canonical")
    op.drop_table("entity_canonical")
    op.drop_index("ix_entity_type", table_name="entity")
    op.drop_table("entity")
    op.drop_index("ix_enrichment_run_reading", table_name="enrichment_run")
    op.drop_table("enrichment_run")
    op.drop_index("ix_enriched_stale", table_name="enriched_fact")
    op.drop_table("enriched_fact")
    op.drop_table("engine_run")
    op.drop_table("embedding_run")
    op.drop_index("ix_conversation_thread_seq", table_name="conversation_thread")
    op.drop_table("conversation_thread")
    op.drop_index("ix_alias_canonical", table_name="canonical_alias")
    op.drop_table("canonical_alias")
    op.drop_index("ix_briefing_run_role_seq", table_name="briefing_run")
    op.drop_table("briefing_run")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    op.execute("DROP EXTENSION IF EXISTS vector")
