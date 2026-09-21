"""Explicit adapters for physical layouts already known by S11 parsers."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from agent.parsers.contracts import DocumentContext, ExtractionStatus, TechnicalFormat
from agent.parsers.darf_pdf import federal_revenue_form_blocks
from agent.parsers.darf_tax_codes import identify_tax
from agent.parsers.das_pdf import has_das_form_layout
from agent.parsers.federal_revenue_guide import (
    FederalRevenue,
    FederalRevenueGuide,
    FederalRevenueGuideExtractor,
    has_federal_revenue_form_layout,
)
from agent.parsers.guide_common import read_pdf_pages
from agent.parsers.layout_framework import ClassificationResult, LayoutExtractionFailure
from agent.parsers.state_guide_pdf import go_dare_51_layout_blocks
from agent.parsers.state_revenue_codes import classify_state_revenue
from agent.parsers.state_revenue_guide import (
    ExtractedStateGuide,
    StateRevenue,
    StateRevenueGuideExtractor,
    has_go_dare_51_layout,
)

DAS_FORM_LAYOUT_ID = "DAS_FORM"
FEDERAL_REVENUE_FORM_LAYOUT_ID = "FEDERAL_REVENUE_FORM"
GO_DARE_51_LAYOUT_ID = "DARE_GO_5_1"


class _KnownLayoutModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LocatedFederalRevenueGuide(_KnownLayoutModel):
    page_number: int
    block_number: int
    guide: FederalRevenueGuide


class FederalRevenueFormExtraction(_KnownLayoutModel):
    documents: tuple[LocatedFederalRevenueGuide, ...]


class LocatedGoDare51Guide(_KnownLayoutModel):
    page_number: int
    block_number: int
    guide: ExtractedStateGuide


class GoDare51LayoutExtraction(_KnownLayoutModel):
    documents: tuple[LocatedGoDare51Guide, ...]


class DasFormLayoutDetector:
    """DAS-like detector only; stable DAS extraction remains parser-specific."""

    layout_id = DAS_FORM_LAYOUT_ID

    def supports_layout(self, context: DocumentContext) -> bool:
        if context.technical_format is not TechnicalFormat.PDF:
            return False
        pages = read_pdf_pages(context.file_path)
        return pages.status is ExtractionStatus.MATCHED and has_das_form_layout("\n".join(pages.pages))


class FederalRevenueFormExtractor:
    """Context adapter over the reusable, text-only federal extractor."""

    layout_id = FEDERAL_REVENUE_FORM_LAYOUT_ID

    def supports_layout(self, context: DocumentContext) -> bool:
        if context.technical_format is not TechnicalFormat.PDF:
            return False
        pages = read_pdf_pages(context.file_path)
        if pages.status is not ExtractionStatus.MATCHED:
            return False
        blocks = federal_revenue_form_blocks(pages.pages)
        return bool(blocks) and all(
            has_federal_revenue_form_layout(text) for _, _, text in blocks
        )

    def extract(self, context: DocumentContext) -> FederalRevenueFormExtraction:
        pages = _pdf_pages(context)
        blocks = federal_revenue_form_blocks(pages)
        if not blocks or not all(has_federal_revenue_form_layout(text) for _, _, text in blocks):
            raise LayoutExtractionFailure(ExtractionStatus.UNSUPPORTED, "UNKNOWN_GUIDE_LAYOUT")
        extractor = FederalRevenueGuideExtractor()
        return FederalRevenueFormExtraction(
            documents=tuple(
                LocatedFederalRevenueGuide(
                    page_number=page,
                    block_number=block,
                    guide=extractor.extract(text),
                )
                for page, block, text in blocks
            )
        )


class GoDare51LayoutExtractor:
    """Context adapter over the DARE 5.1 structural extractor.

    It intentionally recognizes and extracts the shared shell even when the
    current normal-guide parser later excludes a SEFAZ installment.
    """

    layout_id = GO_DARE_51_LAYOUT_ID

    def supports_layout(self, context: DocumentContext) -> bool:
        if context.technical_format is not TechnicalFormat.PDF:
            return False
        pages = read_pdf_pages(context.file_path)
        if pages.status is not ExtractionStatus.MATCHED:
            return False
        blocks = go_dare_51_layout_blocks(pages.pages)
        return bool(blocks) and all(has_go_dare_51_layout(text) for _, _, text in blocks)

    def extract(self, context: DocumentContext) -> GoDare51LayoutExtraction:
        pages = _pdf_pages(context)
        blocks = go_dare_51_layout_blocks(pages)
        if not blocks or not all(has_go_dare_51_layout(text) for _, _, text in blocks):
            raise LayoutExtractionFailure(ExtractionStatus.UNSUPPORTED, "UNKNOWN_GUIDE_LAYOUT")
        extractor = StateRevenueGuideExtractor()
        return GoDare51LayoutExtraction(
            documents=tuple(
                LocatedGoDare51Guide(
                    page_number=page,
                    block_number=block,
                    guide=extractor.extract(text),
                )
                for page, block, text in blocks
            )
        )


class FederalRevenueClassifier:
    """Classify one already extracted federal revenue row."""

    def classify(
        self,
        extracted: FederalRevenue,
        context: DocumentContext,
    ) -> ClassificationResult:
        del context
        tax, source, warning = identify_tax(
            extracted.revenue_code,
            " ".join(filter(None, (extracted.description, extracted.detail_description))),
        )
        known = tax != "UNKNOWN"
        return ClassificationResult(
            classification_id=tax,
            classification_known=known,
            document_family="DARF",
            document_kind=tax,
            confidence=1 if source == "REVENUE_CODE" else 0.75 if source else None,
            warnings=(warning,) if warning else (),
        )


class StateRevenueClassifier:
    """Classify one already extracted DARE revenue row."""

    def classify(
        self,
        extracted: StateRevenue,
        context: DocumentContext,
    ) -> ClassificationResult:
        del context
        tax, kind, source, warnings = classify_state_revenue(
            extracted.revenue_code,
            extracted.description,
            extracted.parent_revenue_code,
            extracted.parent_description,
        )
        known = kind != "UNKNOWN"
        return ClassificationResult(
            classification_id=kind,
            classification_known=known,
            document_family="STATE_GUIDE",
            document_kind=kind,
            confidence=1 if source in {"REVENUE_CODE", "PARENT_AND_REVENUE_CODE"} else 0.75 if source else None,
            warnings=warnings,
        )


def _pdf_pages(context: DocumentContext) -> tuple[str, ...]:
    if context.technical_format is not TechnicalFormat.PDF:
        raise LayoutExtractionFailure(ExtractionStatus.UNSUPPORTED, "LAYOUT_FORMAT_UNSUPPORTED")
    pages = read_pdf_pages(context.file_path)
    if pages.status is ExtractionStatus.INVALID:
        raise LayoutExtractionFailure(ExtractionStatus.INVALID, "INVALID_PDF")
    if pages.status is ExtractionStatus.INCONCLUSIVE:
        raise LayoutExtractionFailure(ExtractionStatus.INCONCLUSIVE, "PDF_TEXT_LAYER_MISSING")
    return pages.pages
