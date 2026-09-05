import hashlib
import hmac
import secrets
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


_CALENDAR_PURPOSE = "calendar_feed"


def create_calendar_token(settings: Settings, *, user_id: int) -> str:
    payload: dict[str, Any] = {"sub": str(user_id), "purpose": _CALENDAR_PURPOSE}
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGORITHM)


def verify_calendar_token(settings: Settings, token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("purpose") != _CALENDAR_PURPOSE:
        return None
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.isdigit():
        return None
    return int(subject)


_EMAIL_VERIFY_PURPOSE = "email_verify"
EMAIL_VERIFY_TTL_HOURS = 24


def new_verification_nonce() -> str:
    return secrets.token_urlsafe(32)


def create_email_verification_token(
    settings: Settings, *, user_id: int, nonce: str, now: datetime | None = None
) -> str:
    issued = now or datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "purpose": _EMAIL_VERIFY_PURPOSE,
        "nonce": nonce,
        "exp": issued + timedelta(hours=EMAIL_VERIFY_TTL_HOURS),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGORITHM)


def verify_email_verification_token(settings: Settings, token: str) -> tuple[int, str] | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("purpose") != _EMAIL_VERIFY_PURPOSE:
        return None
    subject = payload.get("sub")
    nonce = payload.get("nonce")
    if not isinstance(subject, str) or not subject.isdigit() or not isinstance(nonce, str):
        return None
    return int(subject), nonce


_INVITE_PURPOSE = "buyer_invite"
INVITE_TTL_DAYS = 90
INVITE_CODE_LENGTH = 8
_INVITE_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def create_buyer_invite_token(
    settings: Settings,
    *,
    buyer_key: str,
    display_name: str,
    now: datetime | None = None,
) -> str:
    issued = now or datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": buyer_key,
        "name": display_name,
        "purpose": _INVITE_PURPOSE,
        "exp": issued + timedelta(days=INVITE_TTL_DAYS),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGORITHM)


def verify_buyer_invite_token(settings: Settings, token: str) -> tuple[str, str] | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("purpose") != _INVITE_PURPOSE:
        return None
    subject, name = payload.get("sub"), payload.get("name")
    if not isinstance(subject, str) or not subject:
        return None
    return subject, name if isinstance(name, str) else subject


def buyer_invite_code(settings: Settings, buyer_key: str) -> str:
    digest = hmac.new(
        settings.secret_key.encode("utf-8"),
        f"{_INVITE_PURPOSE}:{buyer_key}".encode(),
        hashlib.sha256,
    ).digest()
    size = len(_INVITE_CODE_ALPHABET)
    return "".join(_INVITE_CODE_ALPHABET[byte % size] for byte in digest[:INVITE_CODE_LENGTH])
