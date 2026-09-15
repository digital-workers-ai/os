from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "1637fb788e4e"
down_revision: str | None = "0789004bf675"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("asset", sa.Column("feedback", sa.Text(), nullable=True))
    op.add_column("skill_run", sa.Column("model", sa.String(length=64), nullable=True))
    op.add_column(
        "skill_run",
        sa.Column(
            "tokens_in", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
    )
    op.add_column(
        "skill_run",
        sa.Column(
            "tokens_out", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("skill_run", "tokens_out")
    op.drop_column("skill_run", "tokens_in")
    op.drop_column("skill_run", "model")
    op.drop_column("asset", "feedback")
