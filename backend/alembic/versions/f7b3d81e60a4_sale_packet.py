from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f7b3d81e60a4"
down_revision: str | None = "e4a9c26b17d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sale_packet",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("sale_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("pdf_path", sa.Text(), nullable=True),
        sa.Column("model_json", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('pending', 'ready', 'failed')", name="ck_sale_packet_status"
        ),
    )
    op.create_index("ix_sale_packet_user_id", "sale_packet", ["user_id"])
    op.create_index("ix_sale_packet_user_sale_date", "sale_packet", ["user_id", "sale_date"])


def downgrade() -> None:
    op.drop_index("ix_sale_packet_user_sale_date", table_name="sale_packet")
    op.drop_index("ix_sale_packet_user_id", table_name="sale_packet")
    op.drop_table("sale_packet")
