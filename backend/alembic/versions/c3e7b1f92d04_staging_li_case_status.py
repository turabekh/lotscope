from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3e7b1f92d04"
down_revision: str | None = "b2d5f0a83c17"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "li_event", sa.Column("case_status", sa.String(length=60), nullable=True), schema="staging"
    )


def downgrade() -> None:
    op.drop_column("li_event", "case_status", schema="staging")
