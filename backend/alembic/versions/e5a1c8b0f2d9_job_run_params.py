from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "e5a1c8b0f2d9"
down_revision: str | None = "d3b9f1c72a48"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("job_run", sa.Column("params", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("job_run", "params")
