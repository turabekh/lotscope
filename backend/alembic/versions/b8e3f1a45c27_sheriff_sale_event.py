from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8e3f1a45c27"
down_revision: str | Sequence[str] | None = "a1c7e4f90b62"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sheriff_sale_event",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("parcel_number", sa.String(length=40), nullable=False),
        sa.Column("case_number", sa.String(length=60), nullable=False),
        sa.Column("sale_date", sa.Date(), nullable=True),
        sa.Column("old_status", sa.String(length=60), nullable=True),
        sa.Column("new_status", sa.String(length=60), nullable=True),
        sa.Column("old_sale_date", sa.Date(), nullable=True),
        sa.Column("new_sale_date", sa.Date(), nullable=True),
        sa.Column(
            "observed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sheriff_sale_event_parcel_number", "sheriff_sale_event", ["parcel_number"])
    op.create_index("ix_sheriff_sale_event_case_number", "sheriff_sale_event", ["case_number"])
    op.create_index("ix_sheriff_sale_event_observed_at", "sheriff_sale_event", ["observed_at"])


def downgrade() -> None:
    op.drop_index("ix_sheriff_sale_event_observed_at", table_name="sheriff_sale_event")
    op.drop_index("ix_sheriff_sale_event_case_number", table_name="sheriff_sale_event")
    op.drop_index("ix_sheriff_sale_event_parcel_number", table_name="sheriff_sale_event")
    op.drop_table("sheriff_sale_event")
