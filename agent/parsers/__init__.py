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
from agent.parsers.darf_pdf import DarfDocument, DarfFile, DarfHeader, DarfPdfParser, DarfRevenue, DarfValidation
from agent.parsers.layout_framework import (
    ClassificationResult,
    ComposableDocumentParser,
    DocumentClassifier,
    DocumentLayoutDetector,
    DocumentLayoutExtractor,
    LayoutIdentification,
    LayoutRegistry,
    SanitizedLayoutDiagnostic,
    default_layout_registry,
    sanitized_layout_diagnostic,
)
from agent.parsers.runtime import DocumentParserRuntime, ParserRegistry, default_parser_registry
from agent.parsers.state_guide_pdf import StateGuideDocument, StateGuideFile, StateGuidePdfParser
from agent.parsers.state_revenue_guide import StateComponent, StateGuideHeader, StateGuideValidation, StateRevenue, StateRevenueGuideExtractor

__all__ = [
    "DocumentContext",
    "DocumentClassifier",
    "DocumentLayoutDetector",
    "DocumentLayoutExtractor",
    "DocumentParser",
    "DocumentParserRuntime",
    "DocumentSignal",
    "DasComponent",
    "DasDocument",
    "DasHeader",
    "DasPdfParser",
    "DasValidation",
    "DarfDocument",
    "DarfFile",
    "DarfHeader",
    "DarfPdfParser",
    "DarfRevenue",
    "DarfValidation",
    "ClassificationResult",
    "ComposableDocumentParser",
    "ExtractionStatus",
    "ParserExtraction",
    "ParserRegistry",
    "ParserRunResult",
    "LayoutIdentification",
    "LayoutRegistry",
    "SanitizedLayoutDiagnostic",
    "SignalProvenance",
    "TechnicalFormat",
    "StateComponent",
    "StateGuideDocument",
    "StateGuideFile",
    "StateGuideHeader",
    "StateGuidePdfParser",
    "StateGuideValidation",
    "StateRevenue",
    "StateRevenueGuideExtractor",
    "default_parser_registry",
    "default_layout_registry",
    "sanitized_layout_diagnostic",
]
