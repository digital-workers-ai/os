from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0789004bf675"
down_revision: str | None = "f2ed0c891937"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_run",
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("agent", sa.String(length=16), nullable=False),
        sa.Column("trigger", sa.String(length=16), nullable=False),
        sa.Column("read_detail", sa.Text(), nullable=False),
        sa.Column(
            "proposed", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "duration_ms", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "cost_usd",
            sa.Numeric(precision=10, scale=4),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("ok", sa.Boolean(), nullable=False),
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
        "proposal",
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("slot_date", sa.Date(), nullable=True),
        sa.Column("slot_name", sa.String(length=64), nullable=True),
        sa.Column(
            "reactive", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("skill", sa.String(length=64), nullable=False),
        sa.Column("skill_sha", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'open'"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("seq"),
    )
    op.create_index("ix_proposal_slot_date", "proposal", ["slot_date"], unique=False)
    op.create_index(
        "ix_proposal_status_seq",
        "proposal",
        ["status", sa.literal_column("seq DESC")],
        unique=False,
    )
    op.create_table(
        "slot_skip",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("slot_date", sa.Date(), nullable=False),
        sa.Column("slot_name", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slot_date", "slot_name", name="slot_skip_slot"),
    )
    op.create_table(
        "asset",
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("look", sa.String(length=64), nullable=True),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("proposal_seq", sa.BigInteger(), nullable=True),
        sa.Column("ancestor_ref", sa.String(length=512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["proposal_seq"], ["proposal.seq"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("seq"),
    )
    op.create_index(
        "ix_asset_kind_seq",
        "asset",
        ["kind", sa.literal_column("seq DESC")],
        unique=False,
    )
    op.create_table(
        "proposal_claim",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("proposal_seq", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source_kind", sa.String(length=16), nullable=False),
        sa.Column("source_ref", sa.String(length=512), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["proposal_seq"], ["proposal.seq"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_proposal_claim_proposal", "proposal_claim", ["proposal_seq"], unique=False
    )
    op.create_table(
        "proposal_draft",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("proposal_seq", sa.BigInteger(), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("media_type", sa.String(length=128), nullable=False),
        sa.Column("bytes", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["proposal_seq"], ["proposal.seq"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_proposal_draft_proposal", "proposal_draft", ["proposal_seq"], unique=False
    )
    op.create_table(
        "proposal_evidence",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("proposal_seq", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("ref", sa.String(length=512), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["proposal_seq"], ["proposal.seq"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_proposal_evidence_proposal",
        "proposal_evidence",
        ["proposal_seq"],
        unique=False,
    )
    op.create_table(
        "asset_file",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("asset_seq", sa.BigInteger(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("media_type", sa.String(length=128), nullable=False),
        sa.Column("bytes", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["asset_seq"], ["asset.seq"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "asset_seq", "version", "path", name="asset_file_version_path"
        ),
    )
    op.create_table(
        "skill_run",
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("skill", sa.String(length=64), nullable=False),
        sa.Column("skill_sha", sa.String(length=64), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("caller", sa.String(length=16), nullable=False),
        sa.Column("proposal_seq", sa.BigInteger(), nullable=True),
        sa.Column("asset_seq", sa.BigInteger(), nullable=True),
        sa.Column("stage", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "duration_ms", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "cost_usd",
            sa.Numeric(precision=10, scale=4),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["asset_seq"], ["asset.seq"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["proposal_seq"], ["proposal.seq"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("seq"),
    )
    op.create_index("ix_skill_run_status", "skill_run", ["status"], unique=False)
    op.create_table(
        "skill_run_tool_call",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("skill_run_seq", sa.BigInteger(), nullable=False),
        sa.Column("tool", sa.String(length=64), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column(
            "duration_ms", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["skill_run_seq"], ["skill_run.seq"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_skill_run_tool_call_run",
        "skill_run_tool_call",
        ["skill_run_seq"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_skill_run_tool_call_run", table_name="skill_run_tool_call")
    op.drop_table("skill_run_tool_call")
    op.drop_index("ix_skill_run_status", table_name="skill_run")
    op.drop_table("skill_run")
    op.drop_table("asset_file")
    op.drop_index("ix_proposal_evidence_proposal", table_name="proposal_evidence")
    op.drop_table("proposal_evidence")
    op.drop_index("ix_proposal_draft_proposal", table_name="proposal_draft")
    op.drop_table("proposal_draft")
    op.drop_index("ix_proposal_claim_proposal", table_name="proposal_claim")
    op.drop_table("proposal_claim")
    op.drop_index("ix_asset_kind_seq", table_name="asset")
    op.drop_table("asset")
    op.drop_table("slot_skip")
    op.drop_index("ix_proposal_status_seq", table_name="proposal")
    op.drop_index("ix_proposal_slot_date", table_name="proposal")
    op.drop_table("proposal")
    op.drop_table("agent_run")
