from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from lotscope.parcels.models import OWNER_KEY_EXPRESSION

revision: str = "d4a7e2c8f1b3"
down_revision: str | None = "c3f8a1b6d29e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "parcel",
        sa.Column(
            "owner_key",
            sa.String(length=255),
            sa.Computed(OWNER_KEY_EXPRESSION, persisted=True),
            nullable=True,
        ),
    )
    op.create_index(op.f("ix_parcel_owner_key"), "parcel", ["owner_key"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_parcel_owner_key"), table_name="parcel")
    op.drop_column("parcel", "owner_key")
