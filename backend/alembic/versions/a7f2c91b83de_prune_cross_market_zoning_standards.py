from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7f2c91b83de"
down_revision: str | None = "91c64d647dcf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PRUNE = sa.text(
    "DELETE FROM zoning_standard "
    "WHERE market_code = 'phl' AND code_version = 'hbg-provisional-2026'"
)


def upgrade() -> None:
    op.get_bind().execute(_PRUNE)


def downgrade() -> None:
    pass
