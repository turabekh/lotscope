from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash

from lotscope.core.config import Settings

_hasher = PasswordHash.recommended()
_ALGORITHM = "HS256"


def hash_password(plain_password: str) -> str:
    return _hasher.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _hasher.verify(plain_password, hashed_password)


def create_access_token(
    settings: Settings,
    *,
    subject: str,
    role: str,
    expires_minutes: int | None = None,
) -> str:
    minutes = (
        expires_minutes if expires_minutes is not None else settings.access_token_expire_minutes
    )
    expires_at = datetime.now(UTC) + timedelta(minutes=minutes)
    payload: dict[str, Any] = {"sub": subject, "role": role, "exp": expires_at}
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGORITHM)


def decode_access_token(settings: Settings, token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.secret_key, algorithms=[_ALGORITHM])


_UNSUBSCRIBE_PURPOSE = "digest_unsubscribe"


def create_unsubscribe_token(settings: Settings, *, user_id: int) -> str:
    payload: dict[str, Any] = {"sub": str(user_id), "purpose": _UNSUBSCRIBE_PURPOSE}
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGORITHM)


def verify_unsubscribe_token(settings: Settings, token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("purpose") != _UNSUBSCRIBE_PURPOSE:
        return None
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.isdigit():
        return None
    return int(subject)
