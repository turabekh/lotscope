from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "173d48357669"
down_revision: str | None = "f1a9c72e3b48"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "zba_appeal",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("appeal_number", sa.String(length=40), nullable=False),
        sa.Column("parcel_number", sa.String(length=20), nullable=True),
        sa.Column("appeal_type", sa.String(length=60), nullable=True),
        sa.Column("decision", sa.String(length=40), nullable=True),
        sa.Column("decision_date", sa.Date(), nullable=True),
        sa.Column("address", sa.String(length=160), nullable=True),
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
        sa.Column("source", sa.String(length=120), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("appeal_number", name="uq_zba_appeal_number"),
    )
    op.create_index(op.f("ix_zba_appeal_appeal_type"), "zba_appeal", ["appeal_type"], unique=False)
    op.create_index(op.f("ix_zba_appeal_decision"), "zba_appeal", ["decision"], unique=False)
    op.create_index(
        "ix_zba_appeal_parcel_decision", "zba_appeal", ["parcel_number", "decision"], unique=False
    )
    op.create_index(
        op.f("ix_zba_appeal_parcel_number"), "zba_appeal", ["parcel_number"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_zba_appeal_parcel_number"), table_name="zba_appeal")
    op.drop_index("ix_zba_appeal_parcel_decision", table_name="zba_appeal")
    op.drop_index(op.f("ix_zba_appeal_decision"), table_name="zba_appeal")
    op.drop_index(op.f("ix_zba_appeal_appeal_type"), table_name="zba_appeal")
    op.drop_table("zba_appeal")
