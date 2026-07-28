from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3c45f2553b6"
down_revision: str | None = "d9f3b1c7e485"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "policy_document",
        sa.Column("slug", sa.String(length=40), primary_key=True),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("body_markdown", sa.Text(), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("effective_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "published_at",
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
    )


def downgrade() -> None:
    op.drop_table("policy_document")
