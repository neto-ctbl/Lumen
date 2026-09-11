"""Small offline file-signature probe without fiscal interpretation."""

from __future__ import annotations

from pathlib import Path


PROBE_PREFIX_BYTES = 4096
_ZIP_MAGICS = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
_FORMAT_BY_EXTENSION = {".pdf": "PDF", ".json": "JSON", ".xml": "XML", ".zip": "ZIP"}


def probe_file_format(path: str | Path) -> dict[str, str | bool]:
    """Compare a supported extension with a minimal technical signature."""
    candidate = Path(path)
    expected = _FORMAT_BY_EXTENSION.get(candidate.suffix.casefold())
    with candidate.open("rb") as handle:
        prefix = handle.read(PROBE_PREFIX_BYTES)
    detected = _detect_format(prefix)
    return {"format": expected or "UNKNOWN", "valid": expected is not None and detected == expected}


def _detect_format(prefix: bytes) -> str:
    if prefix.startswith(b"%PDF"):
        return "PDF"
    if prefix.startswith(_ZIP_MAGICS):
        return "ZIP"

    textual = _textual_prefix(prefix)
    if textual is None:
        return "UNKNOWN"
    significant = textual.lstrip()
    if significant.startswith(("{", "[")):
        return "JSON"
    if significant.startswith("<"):
        return "XML"
    return "UNKNOWN"


def _textual_prefix(prefix: bytes) -> str | None:
    if prefix.startswith((b"\xff\xfe", b"\xfe\xff")):
        # Let the BOM select endianness and be consumed by the decoder.
        encoding = "utf-16"
    else:
        encoding = "utf-8-sig"
    try:
        return prefix.decode(encoding)
    except UnicodeDecodeError:
        return None
