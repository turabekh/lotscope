from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e8b2f1a6c9"
down_revision: str | None = "c3f9a1d7b4e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "app_user", sa.Column("onboarded_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("app_user", "onboarded_at")
