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
from agent.parsers.runtime import DocumentParserRuntime, ParserRegistry

__all__ = [
    "DocumentContext",
    "DocumentParser",
    "DocumentParserRuntime",
    "DocumentSignal",
    "ExtractionStatus",
    "ParserExtraction",
    "ParserRegistry",
    "ParserRunResult",
    "SignalProvenance",
    "TechnicalFormat",
]
