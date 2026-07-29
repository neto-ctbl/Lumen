"""
Addon sanitizado para mitmproxy/mitmdump.

Registra método, URL, status, headers sanitizados e corpos textuais limitados.
Não registra Authorization, Cookie, Set-Cookie, senhas, tokens ou chaves conhecidas.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mitmproxy import http

OUTPUT_PATH = Path(
    os.environ.get("DOMINIO_SCAN_HTTP_LOG", "http_flows_sanitized.jsonl")
)

MAX_BODY_CHARS = 25_000

SENSITIVE_HEADER_NAMES = {
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "api-key",
}

SENSITIVE_KEYS = {
    "password",
    "passwd",
    "pwd",
    "senha",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "cookie",
    "set-cookie",
    "apikey",
    "api_key",
    "client_secret",
    "secret",
}

JWT_PATTERN = re.compile(
    r"\beyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\b"
)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def sanitize_headers(headers: http.Headers) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in headers.items(multi=False):
        if key.lower() in SENSITIVE_HEADER_NAMES:
            result[key] = "<REDACTED>"
        else:
            result[key] = JWT_PATTERN.sub("<REDACTED_JWT>", value)
    return result


def redact_json(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                redacted[str(key)] = "<REDACTED>"
            else:
                redacted[str(key)] = redact_json(item)
        return redacted

    if isinstance(value, list):
        return [redact_json(item) for item in value]

    if isinstance(value, str):
        return JWT_PATTERN.sub("<REDACTED_JWT>", value)

    return value


def sanitize_body(message: http.Message | None) -> dict[str, Any] | None:
    if message is None or not message.raw_content:
        return None

    content_type = message.headers.get("content-type", "").lower()
    body_bytes = message.raw_content

    if len(body_bytes) > 2_000_000:
        return {
            "captured": False,
            "reason": "body_too_large",
            "size_bytes": len(body_bytes),
        }

    if not any(
        marker in content_type
        for marker in (
            "json",
            "text/",
            "xml",
            "javascript",
            "x-www-form-urlencoded",
        )
    ):
        return {
            "captured": False,
            "reason": "binary_or_unknown_content_type",
            "content_type": content_type,
            "size_bytes": len(body_bytes),
        }

    text = message.get_text(strict=False)
    if text is None:
        return {
            "captured": False,
            "reason": "text_decode_failed",
            "content_type": content_type,
            "size_bytes": len(body_bytes),
        }

    text = JWT_PATTERN.sub("<REDACTED_JWT>", text)

    if "json" in content_type:
        try:
            parsed = json.loads(text)
            sanitized = redact_json(parsed)
            rendered = json.dumps(
                sanitized,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            return {
                "captured": True,
                "format": "json",
                "truncated": len(rendered) > MAX_BODY_CHARS,
                "text": rendered[:MAX_BODY_CHARS],
                "size_bytes": len(body_bytes),
            }
        except json.JSONDecodeError:
            pass

    for key in SENSITIVE_KEYS:
        text = re.sub(
            rf'(?i)("{re.escape(key)}"\s*:\s*)("[^"]*"|[^,\}}\s]+)',
            rf'\1"<REDACTED>"',
            text,
        )
        text = re.sub(
            rf"(?i)({re.escape(key)}=)[^&\s]+",
            rf"\1<REDACTED>",
            text,
        )

    return {
        "captured": True,
        "format": "text",
        "truncated": len(text) > MAX_BODY_CHARS,
        "text": text[:MAX_BODY_CHARS],
        "size_bytes": len(body_bytes),
    }


def append_record(record: dict[str, Any]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def response(flow: http.HTTPFlow) -> None:
    request = flow.request
    response_message = flow.response

    record = {
        "timestamp": now_iso(),
        "request": {
            "method": request.method,
            "scheme": request.scheme,
            "host": request.pretty_host,
            "port": request.port,
            "path": request.path,
            "pretty_url": request.pretty_url,
            "http_version": request.http_version,
            "headers": sanitize_headers(request.headers),
            "body": sanitize_body(request),
        },
        "response": {
            "status_code": response_message.status_code if response_message else None,
            "reason": response_message.reason if response_message else None,
            "http_version": response_message.http_version if response_message else None,
            "headers": sanitize_headers(response_message.headers)
            if response_message
            else {},
            "body": sanitize_body(response_message),
        },
        "server_address": list(flow.server_conn.address)
        if flow.server_conn and flow.server_conn.address
        else None,
        "error": str(flow.error) if flow.error else None,
    }

    append_record(record)
