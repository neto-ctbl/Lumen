"""Offline, metadata-only parser infrastructure used by the fiscal watcher."""

from agent.parsers.contracts import (
    DocumentContext,
    DocumentParser,
    DocumentSignal,
    ExtractionStatus,
    ParserExtraction,
    ParserRunResult,
    SignalProvenance,
    TechnicalFormat,
)
from agent.parsers.das_pdf import DasComponent, DasDocument, DasHeader, DasPdfParser, DasValidation
from agent.parsers.runtime import DocumentParserRuntime, ParserRegistry, default_parser_registry

__all__ = [
    "DocumentContext",
    "DocumentParser",
    "DocumentParserRuntime",
    "DocumentSignal",
    "DasComponent",
    "DasDocument",
    "DasHeader",
    "DasPdfParser",
    "DasValidation",
    "ExtractionStatus",
    "ParserExtraction",
    "ParserRegistry",
    "ParserRunResult",
    "SignalProvenance",
    "TechnicalFormat",
    "default_parser_registry",
]
