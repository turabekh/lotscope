from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d2f6a8c31e94"
down_revision: str | None = "c9d4b7e21f83"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CANONICAL_ASSUMPTION_KEYS = (
    "construction_cost_per_sqft",
    "soft_cost_pct",
    "selling_cost_pct",
    "target_margin",
    "default_unit_sqft",
    "max_unit_sqft",
)

_BACKFILL_SQL = """
INSERT INTO buy_box (
    user_id, areas, max_bid, target_use, min_lot_sqft, zoning_codes,
    exclude_city_neighbor, exclude_open_violations, exclude_historic, exclude_flood,
    assumptions, owned_parcels, created_at, updated_at
)
SELECT
    p.owner_id,
    '[]'::jsonb,
    NULLIF(p.buy_box ->> 'max_acquisition_price', '')::numeric(12, 2),
    'build',
    NULL,
    '[]'::jsonb,
    false,
    false,
    true,
    true,
    coalesce(
        (SELECT jsonb_object_agg(key, value)
         FROM jsonb_each(p.assumptions)
         WHERE key = ANY(:canonical_keys)
           AND jsonb_typeof(value) = 'number'),
        '{}'::jsonb
    ),
    '[]'::jsonb,
    p.created_at,
    p.updated_at
FROM underwriting_profile AS p
WHERE p.is_default IS TRUE
ON CONFLICT (user_id) DO NOTHING
"""


def upgrade() -> None:
    op.create_table(
        "buy_box",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "areas", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("max_bid", sa.Numeric(12, 2), nullable=True),
        sa.Column("target_use", sa.String(8), nullable=False, server_default="build"),
        sa.Column("min_lot_sqft", sa.Integer(), nullable=True),
        sa.Column(
            "zoning_codes",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "exclude_city_neighbor", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "exclude_open_violations", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("exclude_historic", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("exclude_flood", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "assumptions", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "owned_parcels",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
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
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
        sa.CheckConstraint("target_use IN ('hold', 'build', 'flip')", name="ck_buy_box_target_use"),
    )
    op.execute(
        sa.text(_BACKFILL_SQL).bindparams(
            sa.bindparam("canonical_keys", value=list(_CANONICAL_ASSUMPTION_KEYS))
        )
    )
    op.drop_table("market")


def downgrade() -> None:
    op.create_table(
        "market",
        sa.Column("code", sa.String(10), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("state", sa.String(2), nullable=True),
        sa.Column("url_slug", sa.String(60), nullable=False),
        sa.Column("local_srid", sa.Integer(), nullable=False),
        sa.Column("map_center", postgresql.JSONB(), nullable=False),
        sa.Column("map_bounds", postgresql.JSONB(), nullable=True),
        sa.Column("default_zoom", sa.Numeric(4, 1), nullable=False),
        sa.Column("timezone", sa.String(40), nullable=False),
        sa.Column("recorder_url_template", sa.Text(), nullable=True),
        sa.Column(
            "deal_assumption_overrides",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("coverage_note", sa.Text(), nullable=True),
        sa.Column("launch_status", sa.String(20), nullable=False, server_default="live"),
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
        sa.Column(
            "source_config",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("assessment_ratio", sa.Numeric(6, 4), nullable=True),
        sa.PrimaryKeyConstraint("code"),
        sa.UniqueConstraint("url_slug", name="uq_market_url_slug"),
    )
    op.drop_table("buy_box")
