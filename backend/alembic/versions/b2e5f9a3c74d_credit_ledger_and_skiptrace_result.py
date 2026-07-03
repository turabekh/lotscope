from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b2e5f9a3c74d"
down_revision: str | None = "a1d4e7c2b830"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "credit_ledger",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=40), nullable=False),
        sa.Column("ref", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_credit_ledger_user_id"), "credit_ledger", ["user_id"], unique=False
    )
    op.create_index(
        "uq_credit_ledger_grant_ref",
        "credit_ledger",
        ["user_id", "reason", "ref"],
        unique=True,
        postgresql_where=sa.text("reason <> 'skiptrace_burn' AND ref IS NOT NULL"),
    )
    op.create_table(
        "skiptrace_result",
        sa.Column("owner_key", sa.String(length=255), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column(
            "traced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("owner_key"),
    )


def downgrade() -> None:
    op.drop_table("skiptrace_result")
    op.drop_index("uq_credit_ledger_grant_ref", table_name="credit_ledger")
    op.drop_index(op.f("ix_credit_ledger_user_id"), table_name="credit_ledger")
    op.drop_table("credit_ledger")
