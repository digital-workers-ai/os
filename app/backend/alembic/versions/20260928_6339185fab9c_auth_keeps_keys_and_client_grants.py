from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6339185fab9c"
down_revision: str | None = "445e74372cf6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_key",
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("prefix", sa.String(length=8), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("created_by", sa.String(length=256), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("seq"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_table(
        "mcp_grant",
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("client_id", sa.String(length=256), nullable=False),
        sa.Column("client_name", sa.String(length=256), nullable=True),
        sa.Column("redirect_uri", sa.Text(), nullable=True),
        sa.Column("email", sa.String(length=256), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("seq"),
        sa.UniqueConstraint("client_id", "email", name="uq_mcp_grant_client_email"),
    )


def downgrade() -> None:
    op.drop_table("mcp_grant")
    op.drop_table("api_key")
