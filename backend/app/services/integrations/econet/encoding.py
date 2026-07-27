from __future__ import annotations

import re
import unicodedata

from backend.app.services.integrations.econet.errors import EconetHtmlDecodingError


ALLOWED_ECONET_ENCODINGS = {
    "utf-8": "utf-8",
    "utf8": "utf-8",
    "windows-1252": "cp1252",
    "cp1252": "cp1252",
    "iso-8859-1": "iso-8859-1",
    "latin1": "iso-8859-1",
    "latin-1": "iso-8859-1",
}
CHARSET_RE = re.compile(r"charset\s*=\s*['\"]?\s*([a-z0-9._-]+)", flags=re.IGNORECASE)
META_CHARSET_RE = re.compile(r"<meta[^>]+charset\s*=\s*['\"]?\s*([a-z0-9._-]+)", flags=re.IGNORECASE)
META_HTTP_EQUIV_RE = re.compile(
    r"<meta[^>]+http-equiv\s*=\s*['\"]content-type['\"][^>]+content\s*=\s*['\"][^>]*charset\s*=\s*([a-z0-9._-]+)",
    flags=re.IGNORECASE,
)


def decode_econet_html(content: bytes, content_type: str | None = None) -> str:
    if not content:
        raise EconetHtmlDecodingError("Econet returned empty HTML bytes.")

    candidates: list[str] = []
    if content_type:
        candidates.extend(_extract_allowed_charsets(content_type, CHARSET_RE))

    head_sample = content[:4096].decode("ascii", errors="ignore")
    candidates.extend(_extract_allowed_charsets(head_sample, META_CHARSET_RE))
    candidates.extend(_extract_allowed_charsets(head_sample, META_HTTP_EQUIV_RE))
    candidates.extend(["utf-8", "cp1252", "iso-8859-1"])

    seen: set[str] = set()
    for candidate in candidates:
        normalized = ALLOWED_ECONET_ENCODINGS.get(candidate.lower())
        if normalized is None or normalized in seen:
            continue
        seen.add(normalized)
        try:
            text = content.decode(normalized)
        except UnicodeDecodeError:
            continue
        if "\ufffd" in text:
            continue
        if _contains_unsafe_control_chars(text):
            continue
        return unicodedata.normalize("NFC", text)

    raise EconetHtmlDecodingError("Econet HTML could not be decoded safely with the allowlisted encodings.")


def _extract_allowed_charsets(value: str, pattern: re.Pattern[str]) -> list[str]:
    return [match.group(1).strip().lower() for match in pattern.finditer(value or "")]


def _contains_unsafe_control_chars(value: str) -> bool:
    for char in value:
        if char in "\t\r\n":
            continue
        if unicodedata.category(char) == "Cc":
            return True
    return False
