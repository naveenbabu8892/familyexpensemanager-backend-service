from datetime import timedelta
import pytest
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    decode_access_token,
)


def test_password_hashing_and_verification():
    """Test Argon2 password hashing and verification with pwdlib."""
    password = "SuperSecretPassword123!"
    hashed = get_password_hash(password)

    assert hashed != password
    assert hashed.startswith("$argon2")
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_token_creation_and_decoding():
    """Test JWT token encoding and decoding with PyJWT."""
    payload = {"sub": "user_123", "role": "admin"}
    token = create_access_token(data=payload, expires_delta=timedelta(minutes=15))

    assert isinstance(token, str)
    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "user_123"
    assert decoded["role"] == "admin"
    assert "exp" in decoded


def test_jwt_invalid_token():
    """Test decoding an invalid token returns None."""
    assert decode_access_token("invalid.token.string") is None
