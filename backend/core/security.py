"""
Security & Authentication Core for AegisCode.
Provides password hashing, verification, and JWT access token management.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

# A predictable fallback secret is unsafe for a deployed authentication service.
# Keep local development convenient, but fail closed when production is enabled.
_DEFAULT_DEV_SECRET = "aegiscode-development-only-secret"
_SECRET_ENV = os.getenv("JWT_SECRET") or os.getenv("SECRET_KEY")
_ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()

if _ENVIRONMENT in {"production", "prod"}:
    if not _SECRET_ENV or _SECRET_ENV == _DEFAULT_DEV_SECRET:
        raise RuntimeError(
            "JWT_SECRET (or SECRET_KEY) must be configured with a strong, "
            "unique value when ENVIRONMENT=production."
        )
    SECRET_KEY = _SECRET_ENV
else:
    SECRET_KEY = _SECRET_ENV or _DEFAULT_DEV_SECRET

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against stored bcrypt hash."""
    if not plain_password or not hashed_password:
        return False
    try:
        pwd_bytes = plain_password.encode("utf-8")[:72]
        return bcrypt.checkpw(pwd_bytes, hashed_password.encode("utf-8"))
    except Exception:
        try:
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            return pwd_context.verify(plain_password[:72], hashed_password)
        except Exception:
            return False


def get_password_hash(password: str) -> str:
    """Generate a secure bcrypt hash for a plain-text password."""
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Encode a JWT payload with an expiration claim."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        if expires_delta
        else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "iat": now})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Decode and validate a JWT access token."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
