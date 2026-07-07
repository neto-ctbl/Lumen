from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import bcrypt
from jose import JWTError, jwt

if not hasattr(bcrypt, "__about__"):
    bcrypt.__about__ = SimpleNamespace(__version__=getattr(bcrypt, "__version__", "4.3.0"))

from passlib.context import CryptContext

from backend.app.core.config import get_settings


SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "cookies",
    "password",
    "secret",
    "secret_key",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
}

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def mask_value(value: str, visible_prefix: int = 2, visible_suffix: int = 2) -> str:
    if len(value) <= visible_prefix + visible_suffix:
        return "*" * len(value)
    return f"{value[:visible_prefix]}{'*' * (len(value) - visible_prefix - visible_suffix)}{value[-visible_suffix:]}"


def redact_mapping(data: Mapping[str, object], sensitive_keys: set[str] | None = None) -> dict[str, object]:
    keys = sensitive_keys or SENSITIVE_KEYS
    redacted: dict[str, object] = {}
    for key, value in data.items():
        normalized_key = key.lower()
        if normalized_key in keys and value is not None:
            redacted[key] = "***REDACTED***"
        else:
            redacted[key] = value
    return redacted


def get_password_hash(password: str) -> str:
    try:
        return pwd_context.hash(password)
    except ValueError as exc:
        if "password cannot be longer than 72 bytes" not in str(exc):
            raise
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return pwd_context.verify(plain_password, password_hash)
    except ValueError as exc:
        if "password cannot be longer than 72 bytes" not in str(exc):
            raise
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))


def _build_token_payload(
    *,
    subject: str,
    org_id: int,
    role: str,
    token_type: str,
    token_version: int,
    expires_delta: timedelta,
) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    return {
        "sub": subject,
        "org_id": org_id,
        "role": role,
        "type": token_type,
        "exp": now + expires_delta,
        "iat": now,
        "jti": str(uuid4()),
        "ver": token_version,
    }


def create_access_token(*, subject: str, org_id: int, role: str, token_version: int) -> str:
    settings = get_settings()
    payload = _build_token_payload(
        subject=subject,
        org_id=org_id,
        role=role,
        token_type="access",
        token_version=token_version,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(*, subject: str, org_id: int, role: str, token_version: int) -> str:
    settings = get_settings()
    payload = _build_token_payload(
        subject=subject,
        org_id=org_id,
        role=role,
        token_type="refresh",
        token_version=token_version,
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str, *, expected_type: str | None = None) -> dict[str, object]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Invalid token.") from exc

    token_type = payload.get("type")
    if expected_type is not None and token_type != expected_type:
        raise ValueError("Invalid token type.")

    required_claims = {"sub", "org_id", "role", "type", "exp", "iat", "jti", "ver"}
    missing_claims = [claim for claim in required_claims if claim not in payload]
    if missing_claims:
        raise ValueError(f"Missing token claims: {', '.join(sorted(missing_claims))}.")

    return payload
