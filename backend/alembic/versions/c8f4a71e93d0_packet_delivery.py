from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8f4a71e93d0"
down_revision: str | None = "b5c72e08d3a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sale_packet", sa.Column("emailed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "sale_change_notice",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column(
            "sent_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["event_id"], ["sheriff_sale_event.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "event_id", name="uq_sale_change_notice"),
    )
    op.create_index("ix_sale_change_notice_user_id", "sale_change_notice", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_sale_change_notice_user_id", table_name="sale_change_notice")
    op.drop_table("sale_change_notice")
    op.drop_column("sale_packet", "emailed_at")
