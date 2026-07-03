from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3f7a1e9d260"
down_revision: str | None = "b2e5f9a3c74d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS raw")
    op.execute("CREATE SCHEMA IF NOT EXISTS staging")

    op.create_table(
        "ingest_run",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="running", nullable=False),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("merged_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("event_count", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ingest_run_dataset"), "ingest_run", ["dataset"], unique=False)

    op.create_table(
        "raw_record",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ingest_run_id", sa.Integer(), nullable=False),
        sa.Column("dataset", sa.String(length=120), nullable=False),
        sa.Column("natural_key", sa.String(length=120), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "fetched_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["ingest_run_id"], ["ingest_run.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema="raw",
    )
    op.create_index(
        "ix_raw_record_ingest_run_id", "raw_record", ["ingest_run_id"], unique=False, schema="raw"
    )
    op.create_index("ix_raw_record_dataset", "raw_record", ["dataset"], unique=False, schema="raw")

    op.create_table(
        "parcel_event",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("parcel_number", sa.String(length=20), nullable=False),
        sa.Column("dataset", sa.String(length=120), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("old_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ingest_run_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["parcel_number"], ["parcel.parcel_number"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ingest_run_id"], ["ingest_run.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_parcel_event_parcel_number"), "parcel_event", ["parcel_number"], unique=False
    )
    op.create_index(op.f("ix_parcel_event_code"), "parcel_event", ["code"], unique=False)
    op.create_index(
        op.f("ix_parcel_event_detected_at"), "parcel_event", ["detected_at"], unique=False
    )

    op.create_table(
        "tax",
        sa.Column("parcel_number", sa.String(length=20), nullable=False),
        sa.Column("ingest_run_id", sa.Integer(), nullable=False),
        sa.Column("is_delinquent", sa.Boolean(), nullable=True),
        sa.Column("total_due", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("principal_due", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("years_owed", sa.Integer(), nullable=True),
        sa.Column("lien_count", sa.Integer(), nullable=True),
        sa.Column("in_sheriff_sale", sa.Boolean(), nullable=True),
        sa.Column("as_of_date", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("parcel_number"),
        schema="staging",
    )


def downgrade() -> None:
    op.drop_table("tax", schema="staging")
    op.drop_index(op.f("ix_parcel_event_detected_at"), table_name="parcel_event")
    op.drop_index(op.f("ix_parcel_event_code"), table_name="parcel_event")
    op.drop_index(op.f("ix_parcel_event_parcel_number"), table_name="parcel_event")
    op.drop_table("parcel_event")
    op.drop_index("ix_raw_record_dataset", table_name="raw_record", schema="raw")
    op.drop_index("ix_raw_record_ingest_run_id", table_name="raw_record", schema="raw")
    op.drop_table("raw_record", schema="raw")
    op.drop_index(op.f("ix_ingest_run_dataset"), table_name="ingest_run")
    op.drop_table("ingest_run")
    op.execute("DROP SCHEMA IF EXISTS staging")
    op.execute("DROP SCHEMA IF EXISTS raw")
