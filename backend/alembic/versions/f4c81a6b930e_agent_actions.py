from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f4c81a6b930e"
down_revision: str | None = "e1b7c93df248"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Every row an action tool creates carries the run that created it, so a user can ask
# "why is this in my pipeline?" and be shown the conversation that put it there.
_PROVENANCE_TABLES = ("deal", "saved_parcel", "saved_search", "sale_packet")


def upgrade() -> None:
    op.create_table(
        "agent_alert",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column(
            "target", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("agent_run_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_run.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "kind IN ('sale_status', 'new_violation', 'new_delinquency', 'neighbor_deed', "
            "'zba_filing')",
            name="ck_agent_alert_kind",
        ),
        sa.CheckConstraint(
            "scope IN ('parcel', 'area', 'owned_neighbors')", name="ck_agent_alert_scope"
        ),
    )
    op.create_index("ix_agent_alert_user_id", "agent_alert", ["user_id"])
    op.create_index("ix_agent_alert_user_kind", "agent_alert", ["user_id", "kind"])

    for table in _PROVENANCE_TABLES:
        op.add_column(table, sa.Column("agent_run_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_agent_run",
            table,
            "agent_run",
            ["agent_run_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    for table in _PROVENANCE_TABLES:
        op.drop_constraint(f"fk_{table}_agent_run", table, type_="foreignkey")
        op.drop_column(table, "agent_run_id")
    op.drop_index("ix_agent_alert_user_kind", table_name="agent_alert")
    op.drop_index("ix_agent_alert_user_id", table_name="agent_alert")
    op.drop_table("agent_alert")
