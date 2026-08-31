from __future__ import annotations

from pathlib import Path

from agent.parsers.pdf_text_probe import probe_pdf_text
from backend.tests.watcher_agent_test_utils import write_synthetic_pdf


def test_valid_pdf_with_text_returns_structural_metadata_only(tmp_path: Path) -> None:
    path = tmp_path / "with-text.pdf"
    write_synthetic_pdf(path, text="SYNTHETIC TEXT")
    result = probe_pdf_text(path)
    assert result == {"is_pdf": True, "page_count": 1, "has_extractable_text": True, "text_length": 14}
    assert "text" not in result


def test_valid_pdf_without_text_and_invalid_pdf_are_safe(tmp_path: Path) -> None:
    blank = tmp_path / "blank.pdf"
    invalid = tmp_path / "invalid.pdf"
    write_synthetic_pdf(blank, text="")
    invalid.write_bytes(b"not a pdf")

    assert probe_pdf_text(blank) == {"is_pdf": True, "page_count": 1, "has_extractable_text": False, "text_length": 0}
    assert probe_pdf_text(invalid) == {"is_pdf": False, "page_count": 0, "has_extractable_text": False, "text_length": 0}


def test_encrypted_pdf_is_rejected_without_attempting_decryption(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "encrypted.pdf"
    path.write_bytes(b"%PDF-synthetic")
    reader = type("Reader", (), {"is_encrypted": True, "pages": []})()
    monkeypatch.setattr("agent.parsers.pdf_text_probe.PdfReader", lambda _: reader)
    assert probe_pdf_text(path) == {"is_pdf": False, "page_count": 0, "has_extractable_text": False, "text_length": 0}
