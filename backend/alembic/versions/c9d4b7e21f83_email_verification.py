from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9d4b7e21f83"
down_revision: str | Sequence[str] | None = "b8e3f1a45c27"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BACKFILL_REASON = (
    "The eleven accounts that exist when this migration runs were created before any "
    "verification requirement, through a registration endpoint that never asked for one. "
    "Marking them verified keeps real users working; leaving them NULL would lock every "
    "existing account out of the product on deploy."
)


def upgrade() -> None:
    op.add_column(
        "app_user", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "app_user", sa.Column("email_verification_nonce", sa.String(length=64), nullable=True)
    )
    op.execute(
        sa.text("UPDATE app_user SET email_verified_at = now() WHERE email_verified_at IS NULL")
    )


def downgrade() -> None:
    op.drop_column("app_user", "email_verification_nonce")
    op.drop_column("app_user", "email_verified_at")
