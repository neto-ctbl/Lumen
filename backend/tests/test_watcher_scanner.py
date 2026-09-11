from __future__ import annotations

from pathlib import Path

from agent.watcher.scanner import scan_fiscal_documents
from backend.tests.watcher_agent_test_utils import (
    write_synthetic_json,
    write_synthetic_pdf,
    write_synthetic_xml,
    write_synthetic_zip,
)


def test_scanner_discovers_supported_documents_at_free_depth_only_below_fiscal_root(tmp_path: Path) -> None:
    fiscal = tmp_path / "EMPRESA TESTE" / "Escrita Fiscal"
    paths = [
        fiscal / "08-2026" / "guia.pdf",
        fiscal / "08-2026" / "Importação" / "mit.json",
        fiscal / "_DCTF-Web_" / "08-2026" / "recibo.pdf",
        fiscal / "_REINF_" / "08-2026" / "recibo.pdf",
        fiscal / "Matriz" / "08-2026" / "matriz.pdf",
        fiscal / "Filial" / "08-2026" / "filial.pdf",
        fiscal / "Rubiataba - Matriz" / "08-2026" / "nf.xml",
        fiscal / "Itapaci - Filial" / "08-2026" / "documentos.zip",
        fiscal / "livre" / "profundidade" / "sem" / "periodo" / "documento.pdf",
    ]
    for path in paths:
        if path.suffix == ".pdf":
            path.parent.mkdir(parents=True, exist_ok=True)
            write_synthetic_pdf(path)
        elif path.suffix == ".json":
            write_synthetic_json(path)
        elif path.suffix == ".xml":
            write_synthetic_xml(path)
        else:
            write_synthetic_zip(path)

    temporary = paths[0].with_name("documento.partial.pdf")
    temporary.write_bytes(b"partial")
    unsupported = fiscal / "08-2026" / "ignored.txt"
    unsupported.write_text("ignored", encoding="utf-8")
    for area in ("Departamento Pessoal", "Contabilidade"):
        outside = tmp_path / "EMPRESA TESTE" / area / f"ignored-{area}.pdf"
        outside.parent.mkdir(parents=True, exist_ok=True)
        write_synthetic_pdf(outside)

    discovered = scan_fiscal_documents(tmp_path)

    assert {item.path for item in discovered} == set(paths)
    assert all("\\escrita fiscal\\" in item.normalized_relative_path for item in discovered)


def test_scanner_requires_an_available_root(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    try:
        scan_fiscal_documents(missing)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("scanner accepted an unavailable root")


def test_scanner_accepts_a_direct_fiscal_root_and_prunes_injected_reparse_directory(
    tmp_path: Path, monkeypatch
) -> None:
    fiscal = tmp_path / "EMPRESA TESTE" / "Escrita Fiscal"
    accepted = fiscal / "08-2026" / "accepted.pdf"
    blocked = fiscal / "junction" / "blocked.pdf"
    accepted.parent.mkdir(parents=True)
    blocked.parent.mkdir(parents=True)
    write_synthetic_pdf(accepted)
    write_synthetic_pdf(blocked)
    monkeypatch.setattr("agent.watcher.scanner.is_windows_reparse_point", lambda path: path == blocked.parent)

    assert [item.path for item in scan_fiscal_documents(fiscal)] == [accepted]
