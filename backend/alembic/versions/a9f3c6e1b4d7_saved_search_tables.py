from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "a9f3c6e1b4d7"
down_revision: str | None = "c8e2f5a1d3b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "saved_search",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("criteria", JSONB(), nullable=False),
        sa.Column("alerts_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_saved_search_user_id", "saved_search", ["user_id"], unique=False)
    op.create_table(
        "saved_search_match",
        sa.Column("saved_search_id", sa.Integer(), nullable=False),
        sa.Column("parcel_number", sa.String(length=20), nullable=False),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("notified", sa.Boolean(), server_default="false", nullable=False),
        sa.ForeignKeyConstraint(["saved_search_id"], ["saved_search.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parcel_number"], ["parcel.parcel_number"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("saved_search_id", "parcel_number"),
    )


def downgrade() -> None:
    op.drop_table("saved_search_match")
    op.drop_index("ix_saved_search_user_id", table_name="saved_search")
    op.drop_table("saved_search")
