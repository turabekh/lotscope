from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3e6c9f2a1d8"
down_revision: str | None = "a2d7f4c8e1b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "app_user",
        sa.Column(
            "digest_frequency",
            sa.String(length=10),
            server_default="weekly",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("app_user", "digest_frequency")
