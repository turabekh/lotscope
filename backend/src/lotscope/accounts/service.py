import secrets
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.accounts.schemas import UserCreate
from lotscope.accounts.security import hash_password, new_verification_nonce, verify_password
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
        email_verification_nonce=new_verification_nonce(),
    )
    session.add(user)
    await session.flush()
    return user


async def rotate_verification_nonce(session: AsyncSession, user: User) -> str:
    nonce = new_verification_nonce()
    user.email_verification_nonce = nonce
    await session.flush()
    return nonce


async def verify_email(session: AsyncSession, user_id: int, nonce: str) -> User:
    user = await get_user_by_id(session, user_id)
    if user is None or not user.is_active:
        raise ValidationError("This verification link is no longer valid.")
    if not user.email_verification_nonce or not secrets.compare_digest(
        user.email_verification_nonce, nonce
    ):
        raise ValidationError("This verification link has already been used.")
    user.email_verified_at = datetime.now(UTC)
    user.email_verification_nonce = None
    await session.flush()
    return user


async def authenticate_user(session: AsyncSession, email: str, password: str) -> User:
    user = await get_user_by_email(session, email)
    if user is None or not verify_password(password, user.hashed_password):
        raise AuthError("Invalid email or password.")
    if not user.is_active:
        raise AuthError("This account is inactive.")
    return user


async def get_user_by_stripe_customer(session: AsyncSession, customer_id: str) -> User | None:
    user: User | None = await session.scalar(
        select(User).where(User.stripe_customer_id == customer_id)
    )
    return user
