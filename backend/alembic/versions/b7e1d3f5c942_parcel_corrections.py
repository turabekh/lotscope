from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7e1d3f5c942"
down_revision: str | None = "a2f4c8d19b3e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "parcel_correction",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("parcel_number", sa.String(length=64), nullable=False),
        sa.Column("market_code", sa.String(length=10), nullable=False),
        sa.Column("reported_by", sa.Integer(), nullable=False),
        sa.Column("section", sa.String(length=40), nullable=False),
        sa.Column("field_name", sa.String(length=60), nullable=True),
        sa.Column("verdict_version", sa.String(length=10), nullable=True),
        sa.Column("verdict_computed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("field_status", sa.String(length=20), nullable=True),
        sa.Column("source_label", sa.String(length=60), nullable=True),
        sa.Column("source_as_of", sa.DateTime(timezone=True), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("attachment_ref", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="open", nullable=False),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["reported_by"], ["app_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolved_by"], ["app_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_parcel_correction_parcel_number", "parcel_correction", ["parcel_number"])
    op.create_index("ix_parcel_correction_market_code", "parcel_correction", ["market_code"])
    op.create_index("ix_parcel_correction_reported_by", "parcel_correction", ["reported_by"])
    op.create_index("ix_parcel_correction_resolved_by", "parcel_correction", ["resolved_by"])
    op.create_index("ix_parcel_correction_status", "parcel_correction", ["status"])


def downgrade() -> None:
    op.drop_table("parcel_correction")
