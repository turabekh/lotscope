from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "e8a3c7d1f5b9"
down_revision: str | None = "d6f2b9c4a8e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "parcel_distress",
        sa.Column("parcel_number", sa.String(length=20), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("tier", sa.String(length=20), nullable=False),
        sa.Column("sources", JSONB(), server_default="[]", nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["parcel_number"], ["parcel.parcel_number"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("parcel_number"),
    )
    op.create_index(
        "ix_parcel_distress_score", "parcel_distress", [sa.text("score DESC")], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_parcel_distress_score", table_name="parcel_distress")
    op.drop_table("parcel_distress")
