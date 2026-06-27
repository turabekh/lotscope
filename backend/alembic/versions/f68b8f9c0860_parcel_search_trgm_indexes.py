from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
import geoalchemy2


revision: str = 'f68b8f9c0860'
down_revision: str | None = '15d5d1e5d007'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_index(
        "ix_parcel_address_trgm",
        "parcel",
        ["address"],
        postgresql_using="gin",
        postgresql_ops={"address": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_parcel_owner_trgm",
        "parcel",
        ["owner"],
        postgresql_using="gin",
        postgresql_ops={"owner": "gin_trgm_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_parcel_owner_trgm", table_name="parcel")
    op.drop_index("ix_parcel_address_trgm", table_name="parcel")
