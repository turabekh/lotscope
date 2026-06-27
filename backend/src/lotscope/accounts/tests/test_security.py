import jwt
import pytest

from lotscope.accounts.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from lotscope.core.config import Settings

_SECRET_A = "test-secret-key-that-is-at-least-32-bytes-long"
_SECRET_B = "another-distinct-secret-key-32-bytes-or-more"


def _settings(secret: str = _SECRET_A) -> Settings:
    return Settings(_env_file=None, secret_key=secret)


def test_password_hash_is_verifiable() -> None:
    hashed = hash_password("hunter2-strong")
    assert hashed != "hunter2-strong"
    assert verify_password("hunter2-strong", hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_token_roundtrip_preserves_claims() -> None:
    settings = _settings()
    token = create_access_token(settings, subject="42", role="admin")
    payload = decode_access_token(settings, token)
    assert payload["sub"] == "42"
    assert payload["role"] == "admin"


def test_token_rejects_a_different_secret() -> None:
    token = create_access_token(_settings(_SECRET_A), subject="1", role="user")
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(_settings(_SECRET_B), token)


def test_expired_token_is_rejected() -> None:
    settings = _settings()
    token = create_access_token(settings, subject="1", role="user", expires_minutes=-1)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(settings, token)
