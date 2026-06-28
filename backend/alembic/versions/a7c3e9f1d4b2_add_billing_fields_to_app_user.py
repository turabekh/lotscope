from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7c3e9f1d4b2"
down_revision: str | None = "f5b2d8c1a9e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("app_user", sa.Column("stripe_customer_id", sa.String(length=255), nullable=True))
    op.add_column(
        "app_user", sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True)
    )
    op.add_column("app_user", sa.Column("subscription_status", sa.String(length=40), nullable=True))
    op.create_unique_constraint(
        "uq_app_user_stripe_customer_id", "app_user", ["stripe_customer_id"]
    )
    op.create_index(
        "ix_app_user_stripe_customer_id", "app_user", ["stripe_customer_id"], unique=False
    )
    op.create_index(
        "ix_app_user_stripe_subscription_id", "app_user", ["stripe_subscription_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_app_user_stripe_subscription_id", table_name="app_user")
    op.drop_index("ix_app_user_stripe_customer_id", table_name="app_user")
    op.drop_constraint("uq_app_user_stripe_customer_id", "app_user", type_="unique")
    op.drop_column("app_user", "subscription_status")
    op.drop_column("app_user", "stripe_subscription_id")
    op.drop_column("app_user", "stripe_customer_id")
