from __future__ import annotations

import hashlib
from collections.abc import Mapping


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
