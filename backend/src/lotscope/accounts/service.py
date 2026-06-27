from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.accounts.schemas import UserCreate
from lotscope.accounts.security import hash_password, verify_password
from lotscope.core.errors import AuthError, ValidationError


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.scalar(select(User).where(User.email == email.lower()))
    return result


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def register_user(session: AsyncSession, data: UserCreate) -> User:
    email = data.email.lower()
    if await get_user_by_email(session, email) is not None:
        raise ValidationError("An account with this email already exists.")
    user = User(
        email=email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
    )
    session.add(user)
    await session.flush()
    return user


async def authenticate_user(session: AsyncSession, email: str, password: str) -> User:
    user = await get_user_by_email(session, email)
    if user is None or not verify_password(password, user.hashed_password):
        raise AuthError("Invalid email or password.")
    if not user.is_active:
        raise AuthError("This account is inactive.")
    return user
