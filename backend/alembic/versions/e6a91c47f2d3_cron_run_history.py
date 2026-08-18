from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e6a91c47f2d3"
down_revision: str | None = "d5f8a2c31b74"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("job_run", "triggered_by", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM job_run WHERE triggered_by IS NULL")
    op.alter_column("job_run", "triggered_by", existing_type=sa.Integer(), nullable=False)
