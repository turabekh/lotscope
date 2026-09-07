"""job_run.triggered_by survives deleting the account that triggered it

Revision ID: a4f1c7e29d13
Revises: e3c8a2d5b71f
Create Date: 2026-09-07

Hand-written: autogenerate emits destructive junk against this schema.

The foreign key was ON DELETE CASCADE, so deleting a user deleted the record of every
job that user ever ran. Found by deleting a throwaway admin and watching a successful
588,715-parcel recompute disappear from `job_run` — the work had happened, and the only
row saying who asked for it went with the account.

SET NULL is what the column already means elsewhere: a cron writes `triggered_by` NULL
because nobody triggered it, and a run whose triggerer has been deleted is the same
claim — this ran, and no account here owns it now.
"""

from alembic import op

revision = "a4f1c7e29d13"
down_revision = "e3c8a2d5b71f"
branch_labels = None
depends_on = None

_CONSTRAINT = "job_run_triggered_by_fkey"


def upgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "job_run", type_="foreignkey")
    op.create_foreign_key(
        _CONSTRAINT,
        "job_run",
        "app_user",
        ["triggered_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "job_run", type_="foreignkey")
    op.create_foreign_key(
        _CONSTRAINT,
        "job_run",
        "app_user",
        ["triggered_by"],
        ["id"],
        ondelete="CASCADE",
    )
