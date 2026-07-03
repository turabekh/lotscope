from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7b2c9d4e561"
down_revision: str | None = "e6c9b4a2f18d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rtt",
        sa.Column("parcel_number", sa.String(length=20), nullable=False),
        sa.Column("document_id", sa.String(length=40), nullable=False),
        sa.Column("ingest_run_id", sa.Integer(), nullable=False),
        sa.Column("document_type", sa.String(length=60), nullable=True),
        sa.Column("sale_date", sa.Date(), nullable=True),
        sa.Column("sale_price", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("grantor", sa.Text(), nullable=True),
        sa.Column("grantee", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=120), nullable=True),
        sa.PrimaryKeyConstraint("parcel_number", "document_id"),
        schema="staging",
    )


def downgrade() -> None:
    op.drop_table("rtt", schema="staging")
