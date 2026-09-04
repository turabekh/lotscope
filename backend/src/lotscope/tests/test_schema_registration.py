import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.models import metadata

_IGNORED_SCHEMAS = ("staging", "raw", "topology", "tiger", "tiger_data")
_IGNORED_PREFIXES = ("pre_",)
_IGNORED_TABLES = {"alembic_version", "spatial_ref_sys", "geography_columns", "geometry_columns"}

TABLES_KEPT_WITHOUT_A_MODEL: dict[str, str] = {}


def _registered() -> set[str]:
    return {
        table.name
        for table in metadata.sorted_tables
        if table.schema not in _IGNORED_SCHEMAS
        and table.name not in _IGNORED_TABLES
        and not table.name.startswith(_IGNORED_PREFIXES)
    }


@pytest.mark.integration
async def test_every_migrated_table_is_registered_in_models(db_session: AsyncSession) -> None:
    rows = await db_session.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
        )
    )
    in_database = {
        name
        for name in rows.scalars()
        if name not in _IGNORED_TABLES
        and name not in TABLES_KEPT_WITHOUT_A_MODEL
        and not name.startswith(_IGNORED_PREFIXES)
    }
    in_models = _registered()

    unregistered = sorted(in_database - in_models)
    phantom = sorted(in_models - in_database)
    drifted = unregistered or phantom

    assert not drifted, (
        "lotscope/models.py has drifted from the migrated schema.\n"
        f"  in the database but not imported by models.py: {unregistered}\n"
        f"  declared in models.py but not in the database: {phantom}\n"
        "Alembic autogenerate compares against models.py, so anything missing here "
        "is a table it will propose dropping. A table that is deliberately kept without a "
        "model belongs in TABLES_KEPT_WITHOUT_A_MODEL with the reason it is kept."
    )


@pytest.mark.integration
async def test_a_table_kept_without_a_model_really_is_still_in_the_database(
    db_session: AsyncSession,
) -> None:
    for name, reason in TABLES_KEPT_WITHOUT_A_MODEL.items():
        present = await db_session.scalar(
            text(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = :name"
            ),
            {"name": name},
        )
        assert present == 1, (
            f"{name} is listed as kept-without-a-model but is not in the schema; "
            f"drop the entry. Reason recorded: {reason}"
        )
        assert reason.strip(), f"{name} must record why it is kept"
