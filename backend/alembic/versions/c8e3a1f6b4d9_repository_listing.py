from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8e3a1f6b4d9"
down_revision: str | None = "b7d2f4a9c1e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "repository_listing",
        sa.Column("parcel_number", sa.String(length=40), primary_key=True),
        sa.Column("city_status", sa.String(length=40), nullable=True),
        sa.Column("bid_pending", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("list_as_of", sa.Date(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("external_id", sa.String(length=60), nullable=True),
        sa.Column("source", sa.String(length=60), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["parcel_number"], ["parcel.parcel_number"], ondelete="CASCADE"
        ),
    )


def downgrade() -> None:
    op.drop_table("repository_listing")
