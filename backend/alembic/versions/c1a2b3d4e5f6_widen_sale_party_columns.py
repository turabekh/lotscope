from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c1a2b3d4e5f6"
down_revision: str | None = "b4d28be82e7a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "sale",
        "grantor",
        type_=sa.Text(),
        existing_type=sa.String(length=255),
        existing_nullable=True,
    )
    op.alter_column(
        "sale",
        "grantee",
        type_=sa.Text(),
        existing_type=sa.String(length=255),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "sale",
        "grantee",
        type_=sa.String(length=255),
        existing_type=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "sale",
        "grantor",
        type_=sa.String(length=255),
        existing_type=sa.Text(),
        existing_nullable=True,
    )
