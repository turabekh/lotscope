from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d9b2e5f7c3a1"
down_revision: str | None = "c7f4a9e2b6d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "deal",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("parcel_number", sa.String(length=20), nullable=False),
        sa.Column("stage", sa.String(length=20), server_default="lead", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("target_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parcel_number"], ["parcel.parcel_number"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "parcel_number", name="uq_deal_user_parcel"),
    )
    op.create_index("ix_deal_user_id", "deal", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_deal_user_id", table_name="deal")
    op.drop_table("deal")
