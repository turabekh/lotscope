from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b6b74e29cd61"
down_revision: str | None = "173d48357669"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CHILD_TABLES = (
    "sale",
    "tax_status",
    "sheriff_sale",
    "li_event",
    "parcel_verdict",
    "parcel_distress",
    "parcel_assemblage",
    "parcel_event",
    "saved_parcel",
    "saved_search_match",
    "deal",
    "deed_document",
    "deed_restriction",
    "appeal_packet",
)
_STAGING_TABLES = ("opa", "tax", "rtt", "sheriff_sale", "li_event")

_PHL_SEED = (
    "INSERT INTO market "
    "(code, name, state, url_slug, local_srid, map_center, map_bounds, default_zoom, "
    "timezone, recorder_url_template, deal_assumption_overrides, coverage_note, launch_status, "
    "created_at, updated_at) VALUES "
    "('phl', 'Philadelphia', 'PA', 'philadelphia', 2272, '[-75.1652, 39.9526]'::jsonb, NULL, 13, "
    "'America/New_York', "
    "'https://epay.phila-records.com/phillyepay/web/integration/document/"
    "InstrumentID={document_id}&Guest=true', '{}'::jsonb, NULL, 'live', now(), now())"
)

_VERIFY = """
DO $$
DECLARE
  pre_parcel bigint;
  bad bigint;
  orphan bigint;
BEGIN
  SELECT n INTO pre_parcel FROM _b1_pre WHERE t = 'parcel';
  IF pre_parcel <> (SELECT count(*) FROM parcel) THEN
    RAISE EXCEPTION 'B1: parcel row count changed during migration';
  END IF;
  SELECT count(*) INTO bad FROM parcel WHERE parcel_number NOT LIKE 'phl:%';
  IF bad > 0 THEN RAISE EXCEPTION 'B1: % parcels not phl-prefixed', bad; END IF;
  SELECT count(*) INTO bad FROM sale WHERE parcel_number NOT LIKE 'phl:%';
  IF bad > 0 THEN RAISE EXCEPTION 'B1: % sale rows not phl-prefixed', bad; END IF;
  SELECT count(*) INTO bad FROM parcel_verdict WHERE parcel_number NOT LIKE 'phl:%';
  IF bad > 0 THEN RAISE EXCEPTION 'B1: % verdict rows not phl-prefixed', bad; END IF;
  SELECT count(*) INTO orphan FROM parcel_verdict v
    LEFT JOIN parcel p ON p.parcel_number = v.parcel_number WHERE p.parcel_number IS NULL;
  IF orphan > 0 THEN RAISE EXCEPTION 'B1: % orphan verdict rows', orphan; END IF;
  SELECT count(*) INTO bad FROM parcel WHERE market_code <> 'phl' OR local_key <> substring(parcel_number from 5);
  IF bad > 0 THEN RAISE EXCEPTION 'B1: % parcels with bad market_code/local_key', bad; END IF;
END $$;
"""


def upgrade() -> None:
    op.create_table(
        "market",
        sa.Column("code", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("state", sa.String(length=2), nullable=True),
        sa.Column("url_slug", sa.String(length=60), nullable=False),
        sa.Column("local_srid", sa.Integer(), nullable=False),
        sa.Column("map_center", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("map_bounds", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("default_zoom", sa.Numeric(precision=4, scale=1), nullable=False),
        sa.Column("timezone", sa.String(length=40), nullable=False),
        sa.Column("recorder_url_template", sa.Text(), nullable=True),
        sa.Column(
            "deal_assumption_overrides",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("coverage_note", sa.Text(), nullable=True),
        sa.Column("launch_status", sa.String(length=20), server_default="live", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("code"),
        sa.UniqueConstraint("url_slug", name="uq_market_url_slug"),
    )
    op.execute(_PHL_SEED)

    op.execute(
        "CREATE TEMP TABLE _b1_pre ON COMMIT DROP AS SELECT 'parcel'::text t, count(*) n FROM parcel"
    )

    op.add_column("parcel", sa.Column("market_code", sa.String(length=10), nullable=True))
    for table in _CHILD_TABLES:
        op.drop_constraint(f"{table}_parcel_number_fkey", table, type_="foreignkey")

    op.alter_column("parcel", "parcel_number", type_=sa.String(length=40))
    for table in _CHILD_TABLES:
        op.alter_column(table, "parcel_number", type_=sa.String(length=40))
    op.alter_column("zba_appeal", "parcel_number", type_=sa.String(length=40))
    for table in _STAGING_TABLES:
        op.alter_column(table, "parcel_number", type_=sa.String(length=40), schema="staging")

    op.execute("UPDATE parcel SET parcel_number = 'phl:' || parcel_number, market_code = 'phl'")
    for table in _CHILD_TABLES:
        op.execute(f"UPDATE {table} SET parcel_number = 'phl:' || parcel_number")
    op.execute(
        "UPDATE zba_appeal SET parcel_number = 'phl:' || parcel_number "
        "WHERE parcel_number IS NOT NULL"
    )
    for table in _STAGING_TABLES:
        op.execute(f"UPDATE staging.{table} SET parcel_number = 'phl:' || parcel_number")

    op.execute(
        "ALTER TABLE parcel ADD COLUMN local_key VARCHAR(40) "
        "GENERATED ALWAYS AS (substring(parcel_number from strpos(parcel_number, ':') + 1)) STORED"
    )
    op.alter_column("parcel", "market_code", server_default="phl", nullable=False)
    op.create_index("ix_parcel_market_code", "parcel", ["market_code"])
    op.create_foreign_key(
        "parcel_market_code_fkey", "parcel", "market", ["market_code"], ["code"]
    )

    for table in _CHILD_TABLES:
        op.create_foreign_key(
            f"{table}_parcel_number_fkey",
            table,
            "parcel",
            ["parcel_number"],
            ["parcel_number"],
            ondelete="CASCADE",
        )

    op.execute(_VERIFY)


def downgrade() -> None:
    for table in _CHILD_TABLES:
        op.drop_constraint(f"{table}_parcel_number_fkey", table, type_="foreignkey")
    op.drop_constraint("parcel_market_code_fkey", "parcel", type_="foreignkey")
    op.drop_index("ix_parcel_market_code", table_name="parcel")
    op.drop_column("parcel", "local_key")

    op.execute("UPDATE parcel SET parcel_number = substring(parcel_number from 5)")
    for table in _CHILD_TABLES:
        op.execute(f"UPDATE {table} SET parcel_number = substring(parcel_number from 5)")
    op.execute(
        "UPDATE zba_appeal SET parcel_number = substring(parcel_number from 5) "
        "WHERE parcel_number IS NOT NULL"
    )
    for table in _STAGING_TABLES:
        op.execute(f"UPDATE staging.{table} SET parcel_number = substring(parcel_number from 5)")

    op.drop_column("parcel", "market_code")
    op.alter_column("parcel", "parcel_number", type_=sa.String(length=20))
    for table in _CHILD_TABLES:
        op.alter_column(table, "parcel_number", type_=sa.String(length=20))
    op.alter_column("zba_appeal", "parcel_number", type_=sa.String(length=20))
    for table in _STAGING_TABLES:
        op.alter_column(table, "parcel_number", type_=sa.String(length=20), schema="staging")

    for table in _CHILD_TABLES:
        op.create_foreign_key(
            f"{table}_parcel_number_fkey",
            table,
            "parcel",
            ["parcel_number"],
            ["parcel_number"],
            ondelete="CASCADE",
        )
    op.drop_table("market")
