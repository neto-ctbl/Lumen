from __future__ import annotations

from pathlib import Path

from agent.parsers.contracts import (
    DocumentContext,
    DocumentSignal,
    ExtractionStatus,
    ParserExtraction,
    SignalProvenance,
    TechnicalFormat,
)
from agent.parsers.runtime import DocumentParserRuntime, ParserRegistry
from backend.tests.watcher_agent_test_utils import write_synthetic_json, write_synthetic_pdf


class SyntheticJsonParser:
    name = "synthetic.json"
    version = "1.0.0"
    supported_formats = frozenset({TechnicalFormat.JSON})

    def supports(self, document: DocumentContext) -> bool:
        return '"synthetic": true' in document.file_path.read_text(encoding="utf-8")

    def parse(self, _document: DocumentContext) -> ParserExtraction:
        return ParserExtraction(
            document_family="SYNTHETIC_DOCUMENT",
            extraction_status=ExtractionStatus.MATCHED,
            confidence=0.98,
            signals=(
                DocumentSignal(
                    name="document_period",
                    value="2026-08",
                    provenance=SignalProvenance.CONTENT,
                    confidence=0.98,
                ),
            ),
            structured_data={"synthetic_marker": True},
        )


class UnsupportedJsonParser(SyntheticJsonParser):
    name = "synthetic.unsupported"

    def supports(self, _document: DocumentContext) -> bool:
        return False


class InconclusiveJsonParser(SyntheticJsonParser):
    name = "synthetic.inconclusive"

    def parse(self, _document: DocumentContext) -> ParserExtraction:
        return ParserExtraction(
            document_family="UNKNOWN",
            extraction_status=ExtractionStatus.INCONCLUSIVE,
            confidence=0.2,
            warnings=("SYNTHETIC_INCONCLUSIVE",),
        )


class ExplodingJsonParser(SyntheticJsonParser):
    name = "synthetic.exploding"

    def parse(self, _document: DocumentContext) -> ParserExtraction:
        raise RuntimeError("synthetic sensitive parser detail")


class ExplodingSupportsParser(SyntheticJsonParser):
    name = "synthetic.supports-exploding"

    def supports(self, _document: DocumentContext) -> bool:
        raise RuntimeError("synthetic sensitive support detail")


def _json_document(tmp_path: Path, name: str = "documento.json") -> Path:
    path = tmp_path / name
    write_synthetic_json(path)
    return path


def test_empty_registry_returns_unsupported(tmp_path: Path) -> None:
    result = DocumentParserRuntime().run_file(_json_document(tmp_path))

    assert result.extraction_status is ExtractionStatus.UNSUPPORTED
    assert result.document_family == "UNKNOWN"
    assert result.warnings == ("NO_SUPPORTED_PARSER",)


def test_supported_parser_returns_versioned_structured_result(tmp_path: Path) -> None:
    result = DocumentParserRuntime(ParserRegistry([SyntheticJsonParser()])).run_file(_json_document(tmp_path))

    assert result.parser_name == "synthetic.json"
    assert result.parser_version == "1.0.0"
    assert result.extraction_status is ExtractionStatus.MATCHED
    assert result.document_family == "SYNTHETIC_DOCUMENT"
    assert result.structured_data == {"synthetic_marker": True}


def test_registered_parser_can_decline_document(tmp_path: Path) -> None:
    result = DocumentParserRuntime(ParserRegistry([UnsupportedJsonParser()])).run_file(_json_document(tmp_path))

    assert result.extraction_status is ExtractionStatus.UNSUPPORTED
    assert result.parser_name == "lumen.document-runtime"


def test_supported_parser_can_be_inconclusive(tmp_path: Path) -> None:
    result = DocumentParserRuntime(ParserRegistry([InconclusiveJsonParser()])).run_file(_json_document(tmp_path))

    assert result.extraction_status is ExtractionStatus.INCONCLUSIVE
    assert result.warnings == ("SYNTHETIC_INCONCLUSIVE",)


def test_parser_exception_is_sanitized_and_does_not_escape_runtime(tmp_path: Path) -> None:
    result = DocumentParserRuntime(ParserRegistry([ExplodingJsonParser()])).run_file(_json_document(tmp_path))

    assert result.extraction_status is ExtractionStatus.ERROR
    assert result.warnings == ("PARSER_EXECUTION_ERROR",)
    assert "sensitive" not in result.model_dump_json()


def test_supports_exception_is_isolated_and_next_content_parser_can_match(tmp_path: Path) -> None:
    registry = ParserRegistry([ExplodingSupportsParser(), SyntheticJsonParser()])
    result = DocumentParserRuntime(registry).run_file(_json_document(tmp_path))

    assert result.extraction_status is ExtractionStatus.MATCHED
    assert result.parser_name == "synthetic.json"


def test_wrong_technical_format_is_invalid_before_routing(tmp_path: Path) -> None:
    disguised = _json_document(tmp_path, "documento.pdf")
    result = DocumentParserRuntime(ParserRegistry([SyntheticJsonParser()])).run_file(disguised)

    assert result.extraction_status is ExtractionStatus.INVALID
    assert result.warnings == ("INVALID_FILE_FORMAT",)


def test_valid_but_incompatible_technical_format_is_unsupported(tmp_path: Path) -> None:
    pdf = tmp_path / "documento.pdf"
    write_synthetic_pdf(pdf)

    result = DocumentParserRuntime(ParserRegistry([SyntheticJsonParser()])).run_file(pdf)

    assert result.extraction_status is ExtractionStatus.UNSUPPORTED
    assert result.warnings == ("NO_SUPPORTED_PARSER",)


def test_content_conclusion_wins_while_filename_and_path_remain_provenance(tmp_path: Path) -> None:
    filename_signal = DocumentSignal(
        name="period_from_filename",
        value="2025-01",
        provenance=SignalProvenance.FILENAME,
        confidence=0.3,
    )
    path_signal = DocumentSignal(
        name="period_from_path",
        value="2024-12",
        provenance=SignalProvenance.PATH,
        confidence=0.2,
    )
    result = DocumentParserRuntime(ParserRegistry([SyntheticJsonParser()])).run_file(
        _json_document(tmp_path, "fake-family-2025-01.json"),
        context_signals=(filename_signal, path_signal),
    )

    signals = {(signal.name, signal.provenance) for signal in result.signals}
    assert result.document_family == "SYNTHETIC_DOCUMENT"
    assert ("period_from_filename", SignalProvenance.FILENAME) in signals
    assert ("period_from_path", SignalProvenance.PATH) in signals
    assert ("document_period", SignalProvenance.CONTENT) in signals
    assert ("technical_format", SignalProvenance.FILE_STRUCTURE) in signals


def test_runtime_is_programmatically_composable_with_evidence_registration(tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def registrar(evidence_id: int, payload: dict[str, object]) -> str:
        captured.update(evidence_id=evidence_id, payload=payload)
        return "registered"

    result, response = DocumentParserRuntime(ParserRegistry([SyntheticJsonParser()])).run_and_register(
        _json_document(tmp_path),
        evidence_id=42,
        registrar=registrar,
    )

    assert result.extraction_status is ExtractionStatus.MATCHED
    assert response == "registered"
    assert captured["evidence_id"] == 42
    assert isinstance(captured["payload"], dict)
    assert "file_path" not in captured["payload"]
