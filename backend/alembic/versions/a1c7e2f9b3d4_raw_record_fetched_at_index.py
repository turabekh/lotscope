from collections.abc import Sequence

from alembic import op

revision: str = "a1c7e2f9b3d4"
down_revision: str | None = "f7b2c9d4e561"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_raw_record_fetched_at", "raw_record", ["fetched_at"], schema="raw")


def downgrade() -> None:
    op.drop_index("ix_raw_record_fetched_at", table_name="raw_record", schema="raw")
