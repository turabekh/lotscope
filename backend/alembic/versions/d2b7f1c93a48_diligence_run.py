"""lot diligence: one run per buyer per parcel

Revision ID: d2b7f1c93a48
Revises: c1f4a80d7e35
Create Date: 2026-09-06

Hand-written: autogenerate emits destructive junk against this schema.
"""

import sqlalchemy as sa
from alembic import op

revision = "d2b7f1c93a48"
down_revision = "c1f4a80d7e35"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "diligence_run",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("parcel_number", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("pdf_path", sa.Text(), nullable=True),
        sa.Column("report_json", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_diligence_run_user_id", "diligence_run", ["user_id"])
    op.create_index("ix_diligence_run_parcel_number", "diligence_run", ["parcel_number"])
    op.create_index("ix_diligence_run_user_parcel", "diligence_run", ["user_id", "parcel_number"])


def downgrade() -> None:
    op.drop_index("ix_diligence_run_user_parcel", table_name="diligence_run")
    op.drop_index("ix_diligence_run_parcel_number", table_name="diligence_run")
    op.drop_index("ix_diligence_run_user_id", table_name="diligence_run")
    op.drop_table("diligence_run")
