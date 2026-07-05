from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "9a52d71298f4"
down_revision: str | None = "9fea8e83976d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PHL_SOURCE_CONFIG = (
    "UPDATE market SET source_config = "
    "'{\"carto_sql_url\": \"https://phl.carto.com/api/v2/sql\", "
    '"arcgis_hub_url": "https://data-phl.opendata.arcgis.com"}\'::jsonb '
    "WHERE code = 'phl'"
)


def upgrade() -> None:
    op.add_column(
        "market",
        sa.Column(
            "source_config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
    )
    op.execute(_PHL_SOURCE_CONFIG)


def downgrade() -> None:
    op.drop_column("market", "source_config")
