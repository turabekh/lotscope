from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f3a91c27b0d4"
down_revision: str | None = "ee072d5de889"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("app_user", sa.Column("entity_name", sa.String(length=255), nullable=True))
    op.add_column("app_user", sa.Column("signer_name", sa.String(length=255), nullable=True))
    op.add_column("app_user", sa.Column("signer_phone", sa.String(length=40), nullable=True))
    op.add_column("app_user", sa.Column("signer_email", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("app_user", "signer_email")
    op.drop_column("app_user", "signer_phone")
    op.drop_column("app_user", "signer_name")
    op.drop_column("app_user", "entity_name")
