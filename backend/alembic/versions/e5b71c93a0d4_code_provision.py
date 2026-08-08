from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e5b71c93a0d4"
down_revision: str | None = "c4d81e0a6b52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "code_provision",
        sa.Column(
            "market_code", sa.String(length=10), sa.ForeignKey("market.code"), nullable=False
        ),
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("cite", sa.String(length=64), nullable=False),
        sa.Column("doc", sa.String(length=16), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("title_number", sa.String(length=8), nullable=False),
        sa.Column("parent", sa.String(length=64), nullable=True),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("path", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("heading", sa.String(length=255), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("history", sa.Text(), nullable=True),
        sa.Column("refs", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("note_refs", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("table_data", postgresql.JSONB(), nullable=True),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("source_file", sa.String(length=120), nullable=False),
        sa.Column("source_version", sa.String(length=40), nullable=False),
        sa.Column(
            "loaded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("market_code", "id"),
    )
    op.create_index("ix_code_provision_market_cite", "code_provision", ["market_code", "cite"])
    op.create_index("ix_code_provision_market_parent", "code_provision", ["market_code", "parent"])
    op.create_index(
        "ix_code_provision_market_title_ordinal",
        "code_provision",
        ["market_code", "title_number", "ordinal"],
    )


def downgrade() -> None:
    op.drop_index("ix_code_provision_market_title_ordinal", table_name="code_provision")
    op.drop_index("ix_code_provision_market_parent", table_name="code_provision")
    op.drop_index("ix_code_provision_market_cite", table_name="code_provision")
    op.drop_table("code_provision")
