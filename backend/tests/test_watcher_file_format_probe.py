from __future__ import annotations

from pathlib import Path

import pytest

from agent.parsers.file_format_probe import probe_file_format
from agent.watcher.payload_builder import PayloadBuildError, build_document_candidate_payload
from backend.tests.watcher_agent_test_utils import (
    write_synthetic_json,
    write_synthetic_pdf,
    write_synthetic_xml,
    write_synthetic_zip,
)


@pytest.mark.parametrize(
    ("name", "writer", "expected"),
    [
        ("documento.pdf", write_synthetic_pdf, "PDF"),
        ("documento.json", write_synthetic_json, "JSON"),
        ("documento.xml", write_synthetic_xml, "XML"),
        ("documento.zip", write_synthetic_zip, "ZIP"),
    ],
)
def test_minimal_synthetic_formats_are_recognized(
    tmp_path: Path, name: str, writer, expected: str
) -> None:
    path = tmp_path / "EMPRESA" / "Escrita Fiscal" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    writer(path)
    assert probe_file_format(path) == {"format": expected, "valid": True}


def test_evidently_incompatible_signature_is_rejected_deterministically(tmp_path: Path) -> None:
    path = tmp_path / "EMPRESA" / "Escrita Fiscal" / "falso.pdf"
    write_synthetic_json(path)
    assert probe_file_format(path) == {"format": "PDF", "valid": False}
    with pytest.raises(PayloadBuildError, match="INVALID_FILE_FORMAT"):
        build_document_candidate_payload(tmp_path, path)
