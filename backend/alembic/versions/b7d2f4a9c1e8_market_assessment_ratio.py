from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7d2f4a9c1e8"
down_revision: str | None = "a3f9c1e5d7b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("market", sa.Column("assessment_ratio", sa.Numeric(6, 4), nullable=True))
    op.execute("UPDATE market SET assessment_ratio = 1.0 WHERE code = 'phl'")
    op.execute("UPDATE market SET assessment_ratio = 0.4042 WHERE code = 'hbg'")


def downgrade() -> None:
    op.drop_column("market", "assessment_ratio")
