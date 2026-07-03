from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f1a9c72e3b48"
down_revision: str | None = "e8f1c3a24d70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "appeal_packet",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("parcel_number", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("ref", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parcel_number"], ["parcel.parcel_number"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_appeal_packet_user_id"), "appeal_packet", ["user_id"], unique=False)
    op.create_index(
        "ix_appeal_packet_user_parcel", "appeal_packet", ["user_id", "parcel_number"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_appeal_packet_user_parcel", table_name="appeal_packet")
    op.drop_index(op.f("ix_appeal_packet_user_id"), table_name="appeal_packet")
    op.drop_table("appeal_packet")
