from __future__ import annotations

from pathlib import Path


FIXTURES_DIR = Path("backend/tests/fixtures/nfse")


def test_nfse_fixtures_are_synthetic() -> None:
    for path in FIXTURES_DIR.glob("*.json"):
        text = path.read_text(encoding="utf-8").lower()
        assert "certificado" not in text
        assert "xml" not in text
        assert "@gmail.com" not in text


def test_nfse_fixtures_have_no_certificate() -> None:
    for path in FIXTURES_DIR.glob("*.json"):
        text = path.read_text(encoding="utf-8").lower()
        assert "x509" not in text
