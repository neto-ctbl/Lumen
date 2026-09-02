from __future__ import annotations

from pathlib import Path

from agent.watcher.scanner import scan_fiscal_pdfs
from backend.tests.watcher_agent_test_utils import watcher_pdf_path, write_synthetic_pdf


def test_scanner_discovers_only_grammar_compatible_pdfs(tmp_path: Path) -> None:
    canonical = watcher_pdf_path(tmp_path, name="documento.pdf", nested=True)
    write_synthetic_pdf(canonical)
    ignored_xml = tmp_path / "EMPRESA EXEMPLO" / "Escrita Fiscal" / "07-2026" / "Guias - Impostos e Parcelamentos" / "nota.xml"
    ignored_xml.write_text("<xml />", encoding="utf-8")
    temporary = canonical.with_name("documento.pdf.tmp")
    temporary.write_bytes(b"partial")
    outside = tmp_path / "EMPRESA EXEMPLO" / "Importacao" / "Entrada" / "ignored.pdf"
    outside.parent.mkdir(parents=True)
    write_synthetic_pdf(outside)

    discovered = scan_fiscal_pdfs(tmp_path)

    assert [item.path for item in discovered] == [canonical]
    assert discovered[0].normalized_relative_path.endswith(r"federais\documento.pdf")


def test_scanner_requires_an_available_root(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    try:
        scan_fiscal_pdfs(missing)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("scanner accepted an unavailable root")
