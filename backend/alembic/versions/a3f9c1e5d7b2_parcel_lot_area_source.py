from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3f9c1e5d7b2"
down_revision: str | None = "1219f3299db0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("parcel", sa.Column("lot_area_source", sa.String(length=20), nullable=True))
    op.execute(
        "UPDATE parcel SET lot_area_source = "
        "CASE WHEN market_code = 'hbg' THEN 'geometry' ELSE 'extract' END "
        "WHERE lot_area_sqft IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_column("parcel", "lot_area_source")
