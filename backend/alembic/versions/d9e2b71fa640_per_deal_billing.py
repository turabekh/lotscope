from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d9e2b71fa640"
down_revision: str | None = "c8f4a71e93d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EMPTY_WHEN_DROPPED = (
    "credit_ledger and appeal_packet both held zero rows in production and locally when this "
    "migration was written; no credit and no appeal packet was ever sold, so nothing is "
    "migrated out of them."
)


def upgrade() -> None:
    op.create_table(
        "purchase",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("sku", sa.String(20), nullable=False),
        sa.Column("stripe_session_id", sa.String(255), nullable=False),
        sa.Column("object_ref", sa.String(80), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_session_id", name="uq_purchase_stripe_session"),
        sa.CheckConstraint("sku IN ('packet', 'diligence')", name="ck_purchase_sku"),
    )
    op.create_index("ix_purchase_user_id", "purchase", ["user_id"])
    op.create_index("ix_purchase_user_sku_object", "purchase", ["user_id", "sku", "object_ref"])

    op.create_table(
        "buyer_invite",
        sa.Column("buyer_key", sa.String(255), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("redeemed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["redeemed_by_user_id"], ["app_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("buyer_key"),
        sa.UniqueConstraint("code", name="uq_buyer_invite_code"),
    )
    op.create_index("ix_buyer_invite_code", "buyer_invite", ["code"])

    op.add_column("app_user", sa.Column("comp_until", sa.DateTime(timezone=True), nullable=True))

    op.execute("UPDATE app_user SET tier = 'user' WHERE tier <> 'admin'")
    op.alter_column("app_user", "tier", server_default="user")

    op.drop_table("appeal_packet")
    op.drop_table("credit_ledger")


def downgrade() -> None:
    op.create_table(
        "appeal_packet",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("parcel_number", sa.String(40), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("ref", sa.String(120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_appeal_packet_user_id", "appeal_packet", ["user_id"])
    op.create_table(
        "credit_ledger",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(40), nullable=False),
        sa.Column("ref", sa.String(120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_credit_ledger_user_id", "credit_ledger", ["user_id"])
    op.alter_column("app_user", "tier", server_default="free")
    op.drop_column("app_user", "comp_until")
    op.drop_index("ix_buyer_invite_code", table_name="buyer_invite")
    op.drop_table("buyer_invite")
    op.drop_index("ix_purchase_user_sku_object", table_name="purchase")
    op.drop_index("ix_purchase_user_id", table_name="purchase")
    op.drop_table("purchase")
