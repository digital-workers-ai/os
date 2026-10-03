from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "445e74372cf6"
down_revision: str | None = "f7705ebe21b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "oauth_store",
        sa.Column("collection", sa.Text(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ttl", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("collection", "key"),
    )
    op.create_index(
        "idx_oauth_store_expires_at",
        "oauth_store",
        ["expires_at"],
        unique=False,
        postgresql_where=sa.text("expires_at IS NOT NULL"),
    )
    op.add_column(
        "mcp_call", sa.Column("subject", sa.String(length=256), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("mcp_call", "subject")
    op.drop_index(
        "idx_oauth_store_expires_at",
        table_name="oauth_store",
        postgresql_where=sa.text("expires_at IS NOT NULL"),
    )
    op.drop_table("oauth_store")
