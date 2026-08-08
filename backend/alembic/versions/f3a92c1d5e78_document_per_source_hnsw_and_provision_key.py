from collections.abc import Sequence

from alembic import op

revision: str = "f3a92c1d5e78"
down_revision: str | None = "e5b71c93a0d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SOURCES = ("title14", "phillycode", "deed")


def upgrade() -> None:
    for source in _SOURCES:
        op.execute(
            f"CREATE INDEX ix_document_embedding_hnsw_{source} ON document "
            "USING hnsw (embedding vector_cosine_ops) "
            f"WHERE source = '{source}'"
        )
    op.execute(
        "CREATE UNIQUE INDEX ux_document_source_provision ON document "
        "(source, (doc_metadata->>'provision_id')) "
        "WHERE doc_metadata ? 'provision_id'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ux_document_source_provision")
    for source in _SOURCES:
        op.execute(f"DROP INDEX IF EXISTS ix_document_embedding_hnsw_{source}")
