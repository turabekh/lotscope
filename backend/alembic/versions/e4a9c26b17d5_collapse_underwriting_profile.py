from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e4a9c26b17d5"
down_revision: str | None = "d2f6a8c31e94"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BACKFILL_MAX_BID = """
UPDATE buy_box AS b
SET max_bid = NULLIF(p.buy_box ->> 'max_acquisition_price', '')::numeric(12, 2),
    updated_at = now()
FROM underwriting_profile AS p
WHERE p.owner_id = b.user_id
  AND p.is_default IS TRUE
  AND b.max_bid IS NULL
  AND NULLIF(p.buy_box ->> 'max_acquisition_price', '') IS NOT NULL
"""

_INSERT_MISSING = """
INSERT INTO buy_box (user_id, max_bid, created_at, updated_at)
SELECT p.owner_id,
       NULLIF(p.buy_box ->> 'max_acquisition_price', '')::numeric(12, 2),
       p.created_at,
       p.updated_at
FROM underwriting_profile AS p
WHERE p.is_default IS TRUE
ON CONFLICT (user_id) DO NOTHING
"""


def upgrade() -> None:
    op.execute(sa.text(_INSERT_MISSING))
    op.execute(sa.text(_BACKFILL_MAX_BID))
    op.drop_table("underwriting_profile")


def downgrade() -> None:
    op.create_table(
        "underwriting_profile",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "assumptions", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "buy_box", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
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
        sa.ForeignKeyConstraint(["owner_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "name", name="uq_underwriting_profile_name"),
    )
    op.create_index("ix_underwriting_profile_owner_id", "underwriting_profile", ["owner_id"])
