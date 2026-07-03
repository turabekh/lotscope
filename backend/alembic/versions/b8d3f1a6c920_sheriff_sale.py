from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8d3f1a6c920"
down_revision: str | None = "a1c7e2f9b3d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sheriff_sale",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("parcel_number", sa.String(length=20), nullable=False),
        sa.Column("case_number", sa.String(length=60), nullable=False),
        sa.Column("sale_type", sa.String(length=30), nullable=True),
        sa.Column("sale_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=True),
        sa.Column("opening_bid", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("plaintiff", sa.Text(), nullable=True),
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
        sa.Column("source", sa.String(length=120), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["parcel_number"], ["parcel.parcel_number"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_number", name="uq_sheriff_sale_case"),
    )
    op.create_index(
        op.f("ix_sheriff_sale_parcel_number"), "sheriff_sale", ["parcel_number"], unique=False
    )
    op.create_index(
        "ix_sheriff_sale_parcel_date", "sheriff_sale", ["parcel_number", "sale_date"], unique=False
    )
    op.create_index("ix_sheriff_sale_date", "sheriff_sale", ["sale_date"], unique=False)

    op.create_table(
        "sheriff_sale",
        sa.Column("case_number", sa.String(length=60), nullable=False),
        sa.Column("ingest_run_id", sa.Integer(), nullable=False),
        sa.Column("parcel_number", sa.String(length=20), nullable=False),
        sa.Column("sale_type", sa.String(length=30), nullable=True),
        sa.Column("sale_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=True),
        sa.Column("opening_bid", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("plaintiff", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=120), nullable=True),
        sa.PrimaryKeyConstraint("case_number"),
        schema="staging",
    )


def downgrade() -> None:
    op.drop_table("sheriff_sale", schema="staging")
    op.drop_index("ix_sheriff_sale_date", table_name="sheriff_sale")
    op.drop_index("ix_sheriff_sale_parcel_date", table_name="sheriff_sale")
    op.drop_index(op.f("ix_sheriff_sale_parcel_number"), table_name="sheriff_sale")
    op.drop_table("sheriff_sale")
