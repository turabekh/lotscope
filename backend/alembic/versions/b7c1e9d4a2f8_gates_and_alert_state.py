from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7c1e9d4a2f8"
down_revision: str | None = "f2a8c4d6e10b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_gate_item",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("market_code", sa.String(length=10), nullable=False),
        sa.Column("gate_type", sa.String(length=20), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("satisfied", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("qualifier", sa.String(length=80), nullable=True),
        sa.Column("threshold", sa.String(length=80), nullable=True),
        sa.Column("measured", sa.Text(), nullable=True),
        sa.Column("owner", sa.String(length=80), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("spec_ref", sa.String(length=40), nullable=True),
        sa.Column("as_of", sa.Date(), nullable=True),
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
        sa.ForeignKeyConstraint(["market_code"], ["market.code"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "market_code", "gate_type", "ordinal", name="uq_market_gate_item_market_type_ordinal"
        ),
    )
    op.create_index(
        "ix_market_gate_item_market_code", "market_gate_item", ["market_code"], unique=False
    )
    op.create_table(
        "ops_alert_state",
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("last_job_run_id", sa.Integer(), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("ops_alert_state")
    op.drop_index("ix_market_gate_item_market_code", table_name="market_gate_item")
    op.drop_table("market_gate_item")
