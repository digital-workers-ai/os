from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "cf3e773c7e7c"
down_revision: str | None = "7321f60ce98f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "custom_record",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("app", sa.String(length=64), nullable=False),
        sa.Column("recorded_by", sa.String(length=64), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("saved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_custom_record_app_saved",
        "custom_record",
        ["app", sa.literal_column("saved_at DESC")],
        unique=False,
    )
    op.create_table(
        "custom_record_audit",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("record_id", sa.UUID(), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("actor", sa.String(length=64), nullable=False),
        sa.Column(
            "at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["record_id"], ["custom_record.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("seq"),
    )
    op.create_index(
        "ix_custom_record_audit_record",
        "custom_record_audit",
        ["record_id", "at", "seq"],
        unique=False,
    )
    op.create_table(
        "custom_record_file",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("record_id", sa.UUID(), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("media_type", sa.String(length=128), nullable=False),
        sa.Column("bytes", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["record_id"], ["custom_record.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("record_id", "path", name="custom_record_file_path"),
    )


def downgrade() -> None:
    op.drop_table("custom_record_file")
    op.drop_index("ix_custom_record_audit_record", table_name="custom_record_audit")
    op.drop_table("custom_record_audit")
    op.drop_index("ix_custom_record_app_saved", table_name="custom_record")
    op.drop_table("custom_record")
