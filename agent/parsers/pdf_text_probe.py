"""Structural PDF probe that intentionally never returns extracted text."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader


def probe_pdf_text(path: str | Path) -> dict[str, bool | int]:
    pdf_path = Path(path)
    try:
        with pdf_path.open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                return _invalid_probe()
        reader = PdfReader(str(pdf_path))
        if reader.is_encrypted or len(reader.pages) == 0:
            return _invalid_probe()
        extracted = [page.extract_text() or "" for page in reader.pages]
    except Exception:
        return _invalid_probe()
    text_length = sum(len(text) for text in extracted)
    return {
        "is_pdf": True,
        "page_count": len(reader.pages),
        "has_extractable_text": bool(text_length and any(text.strip() for text in extracted)),
        "text_length": text_length,
    }


def _invalid_probe() -> dict[str, bool | int]:
    return {"is_pdf": False, "page_count": 0, "has_extractable_text": False, "text_length": 0}
