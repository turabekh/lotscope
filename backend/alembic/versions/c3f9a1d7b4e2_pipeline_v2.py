from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3f9a1d7b4e2"
down_revision: str | None = "b7c1e9d4a2f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("deal", sa.Column("next_action", sa.Text(), nullable=True))
    op.add_column("deal", sa.Column("next_action_due", sa.Date(), nullable=True))
    op.add_column("deal", sa.Column("stage_entered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("deal", sa.Column("contact_name", sa.String(length=160), nullable=True))
    op.add_column("deal", sa.Column("contact_phone", sa.String(length=40), nullable=True))
    op.add_column("deal", sa.Column("contact_email", sa.String(length=255), nullable=True))
    op.create_index("ix_deal_next_action_due", "deal", ["next_action_due"], unique=False)

    op.create_table(
        "deal_activity",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("deal_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("from_stage", sa.String(length=20), nullable=True),
        sa.Column("to_stage", sa.String(length=20), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["deal_id"], ["deal.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deal_activity_deal_id", "deal_activity", ["deal_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_deal_activity_deal_id", table_name="deal_activity")
    op.drop_table("deal_activity")
    op.drop_index("ix_deal_next_action_due", table_name="deal")
    op.drop_column("deal", "contact_email")
    op.drop_column("deal", "contact_phone")
    op.drop_column("deal", "contact_name")
    op.drop_column("deal", "stage_entered_at")
    op.drop_column("deal", "next_action_due")
    op.drop_column("deal", "next_action")
