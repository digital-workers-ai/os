from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7321f60ce98f"
down_revision: str | None = "f7705ebe21b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "asset_claim",
        "source_kind",
        existing_type=sa.String(length=16),
        type_=sa.Text(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "asset_claim",
        "source_kind",
        existing_type=sa.Text(),
        type_=sa.String(length=16),
        existing_nullable=False,
    )
