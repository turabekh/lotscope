import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.schemas import UserCreate
from lotscope.accounts.service import authenticate_user, register_user
from lotscope.core.errors import AuthError, ValidationError

pytestmark = pytest.mark.integration


async def test_register_normalizes_email_and_authenticates(db_session: AsyncSession) -> None:
    created = await register_user(
        db_session, UserCreate(email="Jane@Example.com", password="hunter2-strong")
    )
    await db_session.flush()
    assert created.email == "jane@example.com"
    assert created.role == "user"
    assert created.tier == "user"

    authenticated = await authenticate_user(db_session, "jane@example.com", "hunter2-strong")
    assert authenticated.id == created.id


async def test_register_rejects_duplicate_email(db_session: AsyncSession) -> None:
    await register_user(db_session, UserCreate(email="dup@example.com", password="hunter2-strong"))
    await db_session.flush()
    with pytest.raises(ValidationError):
        await register_user(
            db_session, UserCreate(email="DUP@example.com", password="another-strong")
        )


async def test_authenticate_rejects_bad_password(db_session: AsyncSession) -> None:
    await register_user(db_session, UserCreate(email="x@example.com", password="hunter2-strong"))
    await db_session.flush()
    with pytest.raises(AuthError):
        await authenticate_user(db_session, "x@example.com", "wrong-password")


async def test_authenticate_rejects_unknown_email(db_session: AsyncSession) -> None:
    with pytest.raises(AuthError):
        await authenticate_user(db_session, "nobody@example.com", "whatever-1")
