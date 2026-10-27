from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8890dc854596"
down_revision: str | None = "cf3e773c7e7c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "builder_thread",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("app", sa.String(length=64), nullable=True),
        sa.Column("issue_number", sa.Integer(), nullable=True),
        sa.Column("issue_url", sa.String(length=512), nullable=True),
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
        "builder_turn",
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("thread_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("draft", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["thread_id"], ["builder_thread.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("seq"),
    )
    op.create_index(
        "ix_builder_turn_thread_seq", "builder_turn", ["thread_id", "seq"], unique=False
    )
    op.create_table(
        "builder_question",
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("turn_seq", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["turn_seq"], ["builder_turn.seq"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("seq"),
    )
    op.create_index(
        "ix_builder_question_turn",
        "builder_question",
        ["turn_seq", "seq"],
        unique=False,
    )
    op.create_table(
        "builder_suggestion",
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("turn_seq", sa.BigInteger(), nullable=False),
        sa.Column("app", sa.String(length=64), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["turn_seq"], ["builder_turn.seq"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("seq"),
    )
    op.create_index(
        "ix_builder_suggestion_turn",
        "builder_suggestion",
        ["turn_seq", "seq"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_builder_suggestion_turn", table_name="builder_suggestion")
    op.drop_table("builder_suggestion")
    op.drop_index("ix_builder_question_turn", table_name="builder_question")
    op.drop_table("builder_question")
    op.drop_index("ix_builder_turn_thread_seq", table_name="builder_turn")
    op.drop_table("builder_turn")
    op.drop_table("builder_thread")
