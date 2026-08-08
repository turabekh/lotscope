from collections.abc import Sequence

from alembic import op

revision: str = "c8b3e5d197af"
down_revision: str | None = "f3a92c1d5e78"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RENAMES = (
    ("deal_construction_cost_per_sqft", "construction_cost_per_sqft"),
    ("deal_soft_cost_pct", "soft_cost_pct"),
    ("deal_selling_cost_pct", "selling_cost_pct"),
    ("deal_target_margin", "target_margin"),
    ("deal_default_unit_sqft", "default_unit_sqft"),
    ("deal_max_unit_sqft", "max_unit_sqft"),
)


def _rewrite(pairs: Sequence[tuple[str, str]]) -> None:
    for old_key, new_key in pairs:
        op.execute(
            "UPDATE market SET deal_assumption_overrides = "
            f"(deal_assumption_overrides - '{old_key}') "
            f"|| jsonb_build_object('{new_key}', deal_assumption_overrides -> '{old_key}') "
            f"WHERE deal_assumption_overrides ? '{old_key}' "
            f"AND NOT deal_assumption_overrides ? '{new_key}'"
        )
        op.execute(
            "UPDATE market SET deal_assumption_overrides = "
            f"deal_assumption_overrides - '{old_key}' "
            f"WHERE deal_assumption_overrides ? '{old_key}'"
        )


def upgrade() -> None:
    _rewrite(_RENAMES)


def downgrade() -> None:
    _rewrite([(new_key, old_key) for old_key, new_key in _RENAMES])
