from collections.abc import Sequence

from alembic import op

revision: str = "b5c72e08d3a1"
down_revision: str | None = "a3e91d4c72b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD = "target_use IN ('hold', 'build', 'flip')"
_NEW = "target_use IN ('hold', 'build', 'flip', 'assemble')"


def upgrade() -> None:
    op.drop_constraint("ck_buy_box_target_use", "buy_box", type_="check")
    op.create_check_constraint("ck_buy_box_target_use", "buy_box", _NEW)


def downgrade() -> None:
    op.execute("UPDATE buy_box SET target_use = 'build' WHERE target_use = 'assemble'")
    op.drop_constraint("ck_buy_box_target_use", "buy_box", type_="check")
    op.create_check_constraint("ck_buy_box_target_use", "buy_box", _OLD)
