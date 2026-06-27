from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d2e4f6a8b0c1"
down_revision: str | None = "c1a2b3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "zoning_standard",
        sa.Column(
            "requires_master_plan",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("zoning_standard", "requires_master_plan")
