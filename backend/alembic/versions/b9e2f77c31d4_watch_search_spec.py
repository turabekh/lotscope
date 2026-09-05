"""watched searches: a new_match alert kind, and the saved searches migrated into it

Revision ID: b9e2f77c31d4
Revises: a7d3e9c14b28
Create Date: 2026-09-06

Hand-written: autogenerate emits destructive junk against this schema.
"""

import json

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b9e2f77c31d4"
down_revision = "a7d3e9c14b28"
branch_labels = None
depends_on = None

_OLD_KINDS = "'sale_status', 'new_violation', 'new_delinquency', 'neighbor_deed', 'zba_filing'"
_NEW_KINDS = f"{_OLD_KINDS}, 'new_match'"


def _spec(name: str, criteria: dict) -> dict:
    """Carry the saved search across without inventing anything it did not say."""
    zip_code = criteria.get("zip_code")
    return {
        "name": (name or "Watched search")[:120],
        "zip_codes": [zip_code] if zip_code else [],
        "zoning_codes": [c.strip().upper() for c in (criteria.get("zoning_codes") or []) if c.strip()],
        "vacant_only": bool(criteria.get("vacant_only", False)),
        "exclude_city_owned": bool(criteria.get("exclude_city_owned", True)),
        "min_lot_area_sqft": criteria.get("min_lot_area_sqft"),
        "max_lot_area_sqft": criteria.get("max_lot_area_sqft"),
        "min_market_value": criteria.get("min_market_value"),
        "max_market_value": criteria.get("max_market_value"),
        "is_delinquent": criteria.get("is_delinquent"),
    }


def upgrade() -> None:
    op.drop_constraint("ck_agent_alert_kind", "agent_alert", type_="check")
    op.execute(
        f"ALTER TABLE agent_alert ADD CONSTRAINT ck_agent_alert_kind CHECK (kind IN ({_NEW_KINDS}))"
    )

    # Every saved search that was actually alerting becomes a watched search. One that had
    # alerts switched off was not telling anyone anything, so it is not resurrected as a
    # thing that will now email them.
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT s.id, s.user_id, s.name, s.criteria FROM saved_search s "
            "JOIN app_user u ON u.id = s.user_id WHERE s.alerts_enabled IS TRUE"
        )
    ).mappings().all()
    for row in rows:
        criteria = row["criteria"] or {}
        if isinstance(criteria, str):
            criteria = json.loads(criteria)
        connection.execute(
            sa.text(
                "INSERT INTO agent_alert (user_id, kind, scope, target, is_active) "
                "VALUES (:u, 'new_match', 'area', cast(:t AS jsonb), true)"
            ),
            {"u": row["user_id"], "t": json.dumps(_spec(row["name"], criteria))},
        )

    # The searches now live as watches, so the tables go. saved_search_match held cached
    # results of those searches — regenerable, and meaningless without the search.
    op.drop_table("saved_search_match")
    op.drop_table("saved_search")


def downgrade() -> None:
    op.create_table(
        "saved_search",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("market_code", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("criteria", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("alerts_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("agent_run_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_run.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "saved_search_match",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("saved_search_id", sa.Integer(), nullable=False),
        sa.Column("parcel_number", sa.String(length=40), nullable=False),
        sa.Column(
            "first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("notified", sa.Boolean(), server_default="false", nullable=False),
        sa.ForeignKeyConstraint(["saved_search_id"], ["saved_search.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    # The rows themselves are not recoverable; the watches they became are the record.
    op.execute("DELETE FROM agent_alert WHERE kind = 'new_match'")
    op.drop_constraint("ck_agent_alert_kind", "agent_alert", type_="check")
    op.execute(
        f"ALTER TABLE agent_alert ADD CONSTRAINT ck_agent_alert_kind CHECK (kind IN ({_OLD_KINDS}))"
    )
