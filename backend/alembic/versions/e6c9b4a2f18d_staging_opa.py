from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e6c9b4a2f18d"
down_revision: str | None = "d5a8c2f4e137"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "opa",
        sa.Column("parcel_number", sa.String(length=20), nullable=False),
        sa.Column("ingest_run_id", sa.Integer(), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("zip_code", sa.String(length=20), nullable=True),
        sa.Column("owner", sa.String(length=255), nullable=True),
        sa.Column("mailing_address", sa.String(length=255), nullable=True),
        sa.Column("land_use", sa.String(length=120), nullable=True),
        sa.Column("base_zoning_code", sa.String(length=20), nullable=True),
        sa.Column("market_value", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("land_value", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("improvement_value", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("exempt_land", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("exempt_building", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("lot_area_sqft", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("frontage_ft", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("depth_ft", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.PrimaryKeyConstraint("parcel_number"),
        schema="staging",
    )


def downgrade() -> None:
    op.drop_table("opa", schema="staging")
