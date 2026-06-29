from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3f8a1b6d29e"
down_revision: str | None = "b1e7d3a9c52f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "deed_document",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("parcel_number", sa.String(length=20), nullable=False),
        sa.Column("external_id", sa.String(length=80), nullable=True),
        sa.Column("document_type", sa.String(length=80), nullable=True),
        sa.Column("recording_date", sa.Date(), nullable=True),
        sa.Column("blob_key", sa.String(length=255), nullable=True),
        sa.Column("ocr_status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("source", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["parcel_number"], ["parcel.parcel_number"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id", name="uq_deed_document_external"),
    )
    op.create_index("ix_deed_document_parcel_number", "deed_document", ["parcel_number"])
    op.create_index("ix_deed_document_external_id", "deed_document", ["external_id"])

    op.create_table(
        "deed_restriction",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("deed_document_id", sa.Integer(), nullable=False),
        sa.Column("parcel_number", sa.String(length=20), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("citation", sa.String(length=255), nullable=True),
        sa.Column("confidence", sa.String(length=10), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["deed_document_id"], ["deed_document.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parcel_number"], ["parcel.parcel_number"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deed_restriction_deed_document_id", "deed_restriction", ["deed_document_id"])
    op.create_index("ix_deed_restriction_parcel_number", "deed_restriction", ["parcel_number"])


def downgrade() -> None:
    op.drop_index("ix_deed_restriction_parcel_number", table_name="deed_restriction")
    op.drop_index("ix_deed_restriction_deed_document_id", table_name="deed_restriction")
    op.drop_table("deed_restriction")
    op.drop_index("ix_deed_document_external_id", table_name="deed_document")
    op.drop_index("ix_deed_document_parcel_number", table_name="deed_document")
    op.drop_table("deed_document")
