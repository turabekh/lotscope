from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.billing import (
    StripeGateway,
    SubscriptionState,
    granting_price_ids,
    tier_for_subscription,
)
from lotscope.accounts.models import User
from lotscope.accounts.schemas import UserCreate
from lotscope.accounts.security import hash_password, verify_password
from lotscope.core.config import Settings
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


async def get_user_by_stripe_customer(session: AsyncSession, customer_id: str) -> User | None:
    user: User | None = await session.scalar(
        select(User).where(User.stripe_customer_id == customer_id)
    )
    return user


async def ensure_stripe_customer(session: AsyncSession, gateway: StripeGateway, user: User) -> str:
    if user.stripe_customer_id is not None:
        return user.stripe_customer_id
    customer_id = await gateway.create_customer(email=user.email, user_id=user.id)
    user.stripe_customer_id = customer_id
    await session.flush()
    return customer_id


def apply_subscription_state(settings: Settings, user: User, state: SubscriptionState) -> None:
    user.stripe_subscription_id = state.subscription_id
    user.subscription_status = state.status
    user.tier = tier_for_subscription(state.status, state.price_id, granting_price_ids(settings))
