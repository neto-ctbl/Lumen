"""Reusable, explicit layout -> extraction -> classification pipeline.

The framework is intentionally small and in-process.  It is not a plugin
system: production layouts are registered explicitly and deterministically.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Generic, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from agent.parsers.contracts import (
    DocumentContext,
    DocumentSignal,
    ExtractionStatus,
    ParserExtraction,
    SignalProvenance,
    TechnicalFormat,
)
from agent.parsers.file_format_probe import probe_file_format
from agent.parsers.pdf_text_probe import probe_pdf_text

UNKNOWN_LAYOUT_ID = "UNKNOWN"
UNKNOWN_CLASSIFICATION_ID = "UNKNOWN"

TExtracted = TypeVar("TExtracted")
TClassification = TypeVar("TClassification")


@runtime_checkable
class DocumentLayoutDetector(Protocol):
    """Recognize physical structure only, never a fiscal interpretation."""

    layout_id: str

    def supports_layout(self, context: DocumentContext) -> bool: ...


@runtime_checkable
class DocumentLayoutExtractor(Protocol[TExtracted]):
    """Extract the structural fields belonging to one known layout."""

    layout_id: str

    def supports_layout(self, context: DocumentContext) -> bool: ...

    def extract(self, context: DocumentContext) -> TExtracted: ...


@runtime_checkable
class DocumentClassifier(Protocol[TExtracted, TClassification]):
    """Classify already extracted data without reopening the source file."""

    def classify(self, extracted: TExtracted, context: DocumentContext) -> TClassification: ...


class LayoutIdentification(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    layout_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Z][A-Z0-9_]*$")
    matched: bool
    confidence: float | None = Field(default=None, ge=0, le=1)
    technical_format: TechnicalFormat
    signals: tuple[DocumentSignal, ...] = Field(default_factory=tuple, max_length=50)
    warnings: tuple[str, ...] = Field(default_factory=tuple, max_length=20)


class ClassificationResult(BaseModel):
    """Small semantic result; extracted structure stays outside this model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    classification_id: str = Field(
        default=UNKNOWN_CLASSIFICATION_ID,
        min_length=1,
        max_length=100,
        pattern=r"^[A-Z][A-Z0-9_]*$",
    )
    classification_known: bool
    document_family: str = Field(
        default="UNKNOWN",
        min_length=1,
        max_length=100,
        pattern=r"^[A-Z][A-Z0-9_]*$",
    )
    document_kind: str | None = Field(
        default=None,
        max_length=100,
        pattern=r"^[A-Z][A-Z0-9_]*$",
    )
    confidence: float | None = Field(default=None, ge=0, le=1)
    signals: tuple[DocumentSignal, ...] = Field(default_factory=tuple, max_length=100)
    warnings: tuple[str, ...] = Field(default_factory=tuple, max_length=50)


class SanitizedLayoutDiagnostic(BaseModel):
    """Allowlisted diagnostics that cannot reveal document content or path."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    technical_format: str
    page_count: int | None = Field(default=None, ge=0)
    text_available: bool | None = None
    known_layout: bool
    layout_id: str
    classification: str = UNKNOWN_CLASSIFICATION_ID
    classification_known: bool = False
    extraction_status: ExtractionStatus
    warning_codes: tuple[str, ...] = Field(default_factory=tuple, max_length=20)


class LayoutExtractionFailure(Exception):
    """Expected, sanitized extraction outcome for a known pipeline."""

    def __init__(self, status: ExtractionStatus, warning: str) -> None:
        if status not in {
            ExtractionStatus.UNSUPPORTED,
            ExtractionStatus.INCONCLUSIVE,
            ExtractionStatus.INVALID,
        }:
            raise ValueError("layout extraction failures must be non-error outcomes")
        super().__init__(warning)
        self.status = status
        self.warning = warning


class LayoutRegistry:
    """Ordered explicit layout registry; no reflection or dynamic loading."""

    def __init__(self, detectors: Iterable[DocumentLayoutDetector] = ()) -> None:
        self._detectors: list[DocumentLayoutDetector] = []
        for detector in detectors:
            self.register(detector)

    def register(self, detector: DocumentLayoutDetector) -> None:
        if any(existing.layout_id == detector.layout_id for existing in self._detectors):
            raise ValueError(f"layout already registered: {detector.layout_id}")
        self._detectors.append(detector)

    @property
    def layout_ids(self) -> tuple[str, ...]:
        return tuple(detector.layout_id for detector in self._detectors)

    def identify(self, context: DocumentContext) -> LayoutIdentification:
        warnings: list[str] = []
        for detector in self._detectors:
            try:
                matched = detector.supports_layout(context)
            except Exception:
                warnings.append("LAYOUT_DETECTOR_ERROR")
                continue
            if matched:
                return LayoutIdentification(
                    layout_id=detector.layout_id,
                    matched=True,
                    confidence=1,
                    technical_format=context.technical_format,
                    signals=(_layout_signal(detector.layout_id, 1),),
                    warnings=tuple(dict.fromkeys(warnings)),
                )
        return LayoutIdentification(
            layout_id=UNKNOWN_LAYOUT_ID,
            matched=False,
            confidence=None,
            technical_format=context.technical_format,
            signals=(_layout_signal(UNKNOWN_LAYOUT_ID, None),),
            warnings=tuple(dict.fromkeys((*warnings, "UNKNOWN_GUIDE_LAYOUT"))),
        )


class ComposableDocumentParser(Generic[TExtracted]):
    """DocumentParser adapter for one detector/extractor/classifier pipeline."""

    def __init__(
        self,
        *,
        name: str,
        version: str,
        supported_formats: frozenset[TechnicalFormat],
        extractor: DocumentLayoutExtractor[TExtracted],
        classifier: DocumentClassifier[TExtracted, ClassificationResult],
        serialize_extracted: Callable[[TExtracted], dict[str, JsonValue]],
    ) -> None:
        self.name = name
        self.version = version
        self.supported_formats = supported_formats
        self.extractor = extractor
        self.classifier = classifier
        self.serialize_extracted = serialize_extracted

    def supports(self, document: DocumentContext) -> bool:
        return (
            document.technical_format in self.supported_formats
            and self.extractor.supports_layout(document)
        )

    def parse(self, document: DocumentContext) -> ParserExtraction:
        if document.technical_format not in self.supported_formats:
            return _empty(ExtractionStatus.UNSUPPORTED, "LAYOUT_FORMAT_UNSUPPORTED")
        try:
            layout_supported = self.extractor.supports_layout(document)
        except Exception:
            return _empty(ExtractionStatus.ERROR, "LAYOUT_DETECTION_ERROR")
        if not layout_supported:
            return ParserExtraction(
                document_family="UNKNOWN",
                extraction_status=ExtractionStatus.UNSUPPORTED,
                signals=(_layout_signal(UNKNOWN_LAYOUT_ID, None),),
                warnings=("UNKNOWN_GUIDE_LAYOUT",),
            )
        try:
            extracted = self.extractor.extract(document)
        except LayoutExtractionFailure as exc:
            return _empty(exc.status, exc.warning, layout_id=self.extractor.layout_id)
        except Exception:
            return _empty(
                ExtractionStatus.ERROR,
                "LAYOUT_EXTRACTION_ERROR",
                layout_id=self.extractor.layout_id,
            )
        try:
            classification = self.classifier.classify(extracted, document)
        except Exception:
            return _empty(
                ExtractionStatus.ERROR,
                "DOCUMENT_CLASSIFICATION_ERROR",
                layout_id=self.extractor.layout_id,
            )
        try:
            structured_data = self.serialize_extracted(extracted)
        except Exception:
            return _empty(
                ExtractionStatus.ERROR,
                "LAYOUT_SERIALIZATION_ERROR",
                layout_id=self.extractor.layout_id,
            )
        return ParserExtraction(
            document_family=classification.document_family,
            extraction_status=ExtractionStatus.MATCHED,
            confidence=classification.confidence,
            signals=(
                _layout_signal(self.extractor.layout_id, 1),
                DocumentSignal(
                    name="classification_id",
                    value=classification.classification_id,
                    provenance=SignalProvenance.CONTENT,
                    confidence=classification.confidence,
                ),
                DocumentSignal(
                    name="classification_known",
                    value=classification.classification_known,
                    provenance=SignalProvenance.CONTENT,
                    confidence=classification.confidence,
                ),
                *classification.signals,
            ),
            warnings=classification.warnings,
            structured_data=structured_data,
        )


def sanitized_layout_diagnostic(
    file_path: str | Path,
    registry: LayoutRegistry,
) -> SanitizedLayoutDiagnostic:
    """Identify a layout while exposing only allowlisted technical aggregates."""

    candidate = Path(file_path)
    try:
        probe = probe_file_format(candidate)
    except OSError:
        return _diagnostic("UNKNOWN", ExtractionStatus.ERROR, "FILE_UNAVAILABLE")
    if not probe["valid"]:
        return _diagnostic(str(probe["format"]), ExtractionStatus.INVALID, "INVALID_FILE_FORMAT")

    technical_format = TechnicalFormat(str(probe["format"]))
    page_count = None
    text_available = None
    signals: tuple[DocumentSignal, ...] = ()
    if technical_format is TechnicalFormat.PDF:
        pdf_probe = probe_pdf_text(candidate)
        page_count = int(pdf_probe["page_count"])
        text_available = bool(pdf_probe["has_extractable_text"])
        if not pdf_probe["is_pdf"]:
            return _diagnostic("PDF", ExtractionStatus.INVALID, "INVALID_PDF", page_count, text_available)
        if not text_available:
            return _diagnostic(
                "PDF",
                ExtractionStatus.INCONCLUSIVE,
                "PDF_TEXT_LAYER_MISSING",
                page_count,
                text_available,
            )
        signals = (
            DocumentSignal(
                name="pdf_page_count",
                value=page_count,
                provenance=SignalProvenance.FILE_STRUCTURE,
                confidence=1,
            ),
            DocumentSignal(
                name="pdf_has_extractable_text",
                value=text_available,
                provenance=SignalProvenance.FILE_STRUCTURE,
                confidence=1,
            ),
        )
    identified = registry.identify(
        DocumentContext(
            file_path=candidate,
            technical_format=technical_format,
            context_signals=signals,
        )
    )
    return SanitizedLayoutDiagnostic(
        technical_format=technical_format.value,
        page_count=page_count,
        text_available=text_available,
        known_layout=identified.matched,
        layout_id=identified.layout_id,
        extraction_status=(ExtractionStatus.MATCHED if identified.matched else ExtractionStatus.UNSUPPORTED),
        warning_codes=identified.warnings,
    )


def default_layout_registry() -> LayoutRegistry:
    """Return known layouts in deterministic precedence order."""

    from agent.parsers.known_layouts import (
        DasFormLayoutDetector,
        FederalRevenueFormExtractor,
        GoDare51LayoutExtractor,
    )

    return LayoutRegistry(
        (
            DasFormLayoutDetector(),
            FederalRevenueFormExtractor(),
            GoDare51LayoutExtractor(),
        )
    )


def _layout_signal(layout_id: str, confidence: float | None) -> DocumentSignal:
    return DocumentSignal(
        name="layout_id",
        value=layout_id,
        provenance=SignalProvenance.FILE_STRUCTURE,
        confidence=confidence,
    )


def _empty(
    status: ExtractionStatus,
    warning: str,
    *,
    layout_id: str = UNKNOWN_LAYOUT_ID,
) -> ParserExtraction:
    return ParserExtraction(
        document_family="UNKNOWN",
        extraction_status=status,
        signals=(_layout_signal(layout_id, 1 if layout_id != UNKNOWN_LAYOUT_ID else None),),
        warnings=(warning,),
    )


def _diagnostic(
    technical_format: str,
    status: ExtractionStatus,
    warning: str,
    page_count: int | None = None,
    text_available: bool | None = None,
) -> SanitizedLayoutDiagnostic:
    return SanitizedLayoutDiagnostic(
        technical_format=technical_format,
        page_count=page_count,
        text_available=text_available,
        known_layout=False,
        layout_id=UNKNOWN_LAYOUT_ID,
        extraction_status=status,
        warning_codes=(warning,),
    )
