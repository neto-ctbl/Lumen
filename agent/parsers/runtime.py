"""Small in-process registry and failure-isolated document parser runtime."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

from agent.parsers.contracts import (
    DocumentContext,
    DocumentParser,
    DocumentSignal,
    ExtractionStatus,
    ParserRunResult,
    SignalProvenance,
    TechnicalFormat,
)
from agent.parsers.file_format_probe import probe_file_format


RUNTIME_PARSER_NAME = "lumen.document-runtime"
RUNTIME_PARSER_VERSION = "1"


class ParserRegistry:
    """Ordered registry; deliberately not a dynamic plugin system."""

    def __init__(self, parsers: Iterable[DocumentParser] = ()) -> None:
        self._parsers: list[DocumentParser] = []
        for parser in parsers:
            self.register(parser)

    def register(self, parser: DocumentParser) -> None:
        key = (parser.name, parser.version)
        if any((existing.name, existing.version) == key for existing in self._parsers):
            raise ValueError(f"parser already registered: {parser.name}@{parser.version}")
        self._parsers.append(parser)

    def parsers_for(self, technical_format: TechnicalFormat) -> tuple[DocumentParser, ...]:
        return tuple(parser for parser in self._parsers if technical_format in parser.supported_formats)


class DocumentParserRuntime:
    """Run a parser against one local file without propagating parser failures."""

    def __init__(self, registry: ParserRegistry | None = None) -> None:
        self.registry = registry or ParserRegistry()

    def run_file(
        self,
        file_path: str | Path,
        *,
        context_signals: Iterable[DocumentSignal] = (),
    ) -> ParserRunResult:
        candidate = Path(file_path)
        supplied_signals = tuple(context_signals)
        try:
            probe = probe_file_format(candidate)
        except OSError:
            return _runtime_result(ExtractionStatus.ERROR, supplied_signals, "FILE_UNAVAILABLE")

        if not probe["valid"]:
            return _runtime_result(ExtractionStatus.INVALID, supplied_signals, "INVALID_FILE_FORMAT")

        technical_format = TechnicalFormat(str(probe["format"]))
        technical_signal = DocumentSignal(
            name="technical_format",
            value=technical_format.value,
            provenance=SignalProvenance.FILE_STRUCTURE,
            confidence=1,
        )
        document = DocumentContext(
            file_path=candidate,
            technical_format=technical_format,
            context_signals=(*supplied_signals, technical_signal),
        )
        first_support_error: DocumentParser | None = None
        for parser in self.registry.parsers_for(technical_format):
            try:
                supported = parser.supports(document)
            except Exception:  # A third-party parser failure must not stop the watcher.
                first_support_error = first_support_error or parser
                continue
            if not supported:
                continue
            try:
                extraction = parser.parse(document)
            except Exception:  # The result is intentionally sanitized; no document content is logged.
                return _parser_error(parser, document.context_signals, "PARSER_EXECUTION_ERROR")
            return ParserRunResult(
                parser_name=parser.name,
                parser_version=parser.version,
                document_family=extraction.document_family,
                extraction_status=extraction.extraction_status,
                confidence=extraction.confidence,
                signals=(*document.context_signals, *extraction.signals),
                warnings=extraction.warnings,
                structured_data=extraction.structured_data,
            )

        if first_support_error is not None:
            return _parser_error(first_support_error, document.context_signals, "PARSER_SUPPORTS_ERROR")
        return _runtime_result(ExtractionStatus.UNSUPPORTED, document.context_signals, "NO_SUPPORTED_PARSER")

    def run_and_register(
        self,
        file_path: str | Path,
        *,
        evidence_id: int,
        registrar: Callable[[int, dict[str, object]], object],
        context_signals: Iterable[DocumentSignal] = (),
    ) -> tuple[ParserRunResult, object]:
        """Programmatic bridge for a future live or historical executor."""
        result = self.run_file(file_path, context_signals=context_signals)
        response = registrar(evidence_id, result.to_backend_payload())
        return result, response


def _runtime_result(
    status: ExtractionStatus,
    signals: tuple[DocumentSignal, ...],
    warning: str,
) -> ParserRunResult:
    return ParserRunResult(
        parser_name=RUNTIME_PARSER_NAME,
        parser_version=RUNTIME_PARSER_VERSION,
        document_family="UNKNOWN",
        extraction_status=status,
        confidence=None,
        signals=signals,
        warnings=(warning,),
        structured_data={},
    )


def _parser_error(
    parser: DocumentParser,
    signals: tuple[DocumentSignal, ...],
    warning: str,
) -> ParserRunResult:
    return ParserRunResult(
        parser_name=parser.name,
        parser_version=parser.version,
        document_family="UNKNOWN",
        extraction_status=ExtractionStatus.ERROR,
        confidence=None,
        signals=signals,
        warnings=(warning,),
        structured_data={},
    )
