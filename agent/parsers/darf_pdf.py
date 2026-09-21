"""Content-first DARF classifier consuming the reusable federal layout extractor."""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, ConfigDict

from agent.parsers.contracts import (
    DocumentContext, DocumentSignal, ExtractionStatus, ParserExtraction,
    SignalProvenance, TechnicalFormat,
)
from agent.parsers.darf_tax_codes import identify_tax
from agent.parsers.federal_revenue_guide import (
    COMPOSITION_LABEL, FederalGuideHeader, FederalGuideValidation, FederalRevenue,
    FederalRevenueGuideExtractor, has_federal_revenue_form_layout, validate_totals,
)
from agent.parsers.guide_common import read_pdf_pages, search_text

DARF_PARSER_NAME = "lumen.darf-pdf"
DARF_PARSER_VERSION = "1"
_INSTALLMENT_RE = re.compile(r"\b(?:PGFN|SISPAR|PARCSN|PARC|PARCELAMENTO|PARCELA|PERT|RELP|SIMEI)\b")

# Public DARF-specific names, with neutral field contracts reusable by installments.
DarfHeader = FederalGuideHeader
DarfRevenue = FederalRevenue
DarfValidation = FederalGuideValidation


class DarfDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    header: DarfHeader
    revenues: tuple[DarfRevenue, ...]
    validation: DarfValidation
    page_numbers: tuple[int, ...]
    block_numbers: tuple[int, ...]
    warning_codes: tuple[str, ...] = ()


class DarfFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    documents: tuple[DarfDocument, ...]


def _has_signature(text: str) -> bool:
    normalized = search_text(text)
    # Check exclusion before recognizing the shared federal shell. Searching the
    # documentary body also covers programs identified outside Observacoes.
    if _INSTALLMENT_RE.search(normalized) or "DIVIDA ATIVA" in normalized or "DIV.ATIVA" in normalized:
        return False
    return has_federal_revenue_form_layout(text)


def federal_revenue_form_blocks(pages: tuple[str, ...]) -> tuple[tuple[int, int, str], ...] | None:
    """Split complete federal-form pages into physical document blocks."""
    blocks: list[tuple[int, int, str]] = []
    for page_number, text in enumerate(pages, 1):
        lines = text.splitlines()
        starts = [i for i, line in enumerate(lines) if search_text(line).startswith("DOCUMENTO DE ARRECADACAO")]
        page_blocks = []
        for block_number, start in enumerate(starts, 1):
            end = starts[block_number] if block_number < len(starts) else len(lines)
            candidate = "\n".join(lines[start:end])
            if COMPOSITION_LABEL in search_text(candidate):
                page_blocks.append((page_number, block_number, candidate))
        # Do not silently ignore an unreadable/mixed/unknown page in a bundle.
        if not page_blocks:
            return None
        blocks.extend(page_blocks)
    return tuple(blocks)


def _blocks(pages: tuple[str, ...]) -> tuple[tuple[int, int, str], ...] | None:
    return federal_revenue_form_blocks(pages)


class DarfPdfParser:
    name = DARF_PARSER_NAME
    version = DARF_PARSER_VERSION
    supported_formats = frozenset({TechnicalFormat.PDF})

    def supports(self, document: DocumentContext) -> bool:
        if document.technical_format is not TechnicalFormat.PDF:
            return False
        content = read_pdf_pages(document.file_path)
        if content.status is not ExtractionStatus.MATCHED:
            return False
        blocks = _blocks(content.pages)
        return bool(blocks) and all(_has_signature(text) for _, _, text in blocks)

    def parse(self, document: DocumentContext) -> ParserExtraction:
        if document.technical_format is not TechnicalFormat.PDF:
            return _empty(ExtractionStatus.UNSUPPORTED, "DARF_FORMAT_UNSUPPORTED")
        content = read_pdf_pages(document.file_path)
        if content.status is ExtractionStatus.INVALID:
            return _empty(ExtractionStatus.INVALID, "INVALID_PDF")
        if content.status is ExtractionStatus.INCONCLUSIVE:
            return _empty(ExtractionStatus.INCONCLUSIVE, "PDF_TEXT_LAYER_MISSING")
        blocks = _blocks(content.pages)
        if not blocks or not all(_has_signature(text) for _, _, text in blocks):
            return _empty(ExtractionStatus.UNSUPPORTED, "DARF_SIGNATURE_NOT_FOUND_OR_EXCLUDED")
        if len(blocks) > 64:
            return _empty(ExtractionStatus.INCONCLUSIVE, "DARF_DOCUMENT_LIMIT")
        try:
            return self._parse_blocks(blocks)
        except Exception:
            return _empty(ExtractionStatus.ERROR, "DARF_EXTRACTION_ERROR")

    def _parse_blocks(self, blocks: tuple[tuple[int, int, str], ...]) -> ParserExtraction:
        documents: list[DarfDocument] = []
        extractor = FederalRevenueGuideExtractor()
        for page, block, text in blocks:
            guide = extractor.extract(text)
            warnings = [f"DARF_{code}" for code in guide.warning_codes]
            rows = []
            for row in guide.revenues:
                tax, source, warning = identify_tax(row.revenue_code, " ".join(filter(None, (row.description, row.detail_description))))
                rows.append(row.model_copy(update={"tax": tax, "tax_identification_source": source}))
                if warning:
                    warnings.append(warning)
            current = DarfDocument(header=guide.header, revenues=tuple(rows), validation=guide.validation,
                                   page_numbers=(page,), block_numbers=(block,), warning_codes=tuple(dict.fromkeys(warnings)))
            # Only explicit documentary identity AND identical header permit
            # joining repeated-header continuation pages. No filename/page guess.
            same_number = [i for i, existing in enumerate(documents)
                           if current.header.document_number and existing.header.document_number == current.header.document_number]
            merge = next((i for i in same_number if documents[i].header == current.header), None)
            if merge is not None:
                previous = documents[merge]
                duplicate = previous.revenues == current.revenues
                revenues = previous.revenues if duplicate else (*previous.revenues, *current.revenues)
                codes = tuple(dict.fromkeys((*previous.warning_codes, *current.warning_codes,
                                            *(("DARF_REPEATED_DOCUMENT_BLOCK",) if duplicate else ()))))
                validation = validate_totals(previous.header, revenues)
                codes = tuple(code for code in codes if code != "DARF_REVENUE_TOTAL_MISMATCH")
                if validation.sum_matches_total is False:
                    codes = (*codes, "DARF_REVENUE_TOTAL_MISMATCH")
                documents[merge] = previous.model_copy(update={
                    "revenues": tuple(revenues), "validation": validation, "warning_codes": codes,
                    "page_numbers": (*previous.page_numbers, page), "block_numbers": (*previous.block_numbers, block),
                })
            else:
                if same_number:
                    current = current.model_copy(update={"warning_codes": (*current.warning_codes, "DARF_DOCUMENT_NUMBER_CONFLICT")})
                documents.append(current)
        envelope = DarfFile(documents=tuple(documents))
        warnings = tuple(dict.fromkeys(code for doc in documents for code in doc.warning_codes))
        # Confidence is extraction quality only; a partial bundle takes the least
        # complete document's score, not the best document's score.
        confidence = min(_confidence(doc) for doc in documents)
        signals = (
            DocumentSignal(name="period_from_content", provenance=SignalProvenance.CONTENT, confidence=confidence,
                           value=[{"document_index": i, "period": doc.header.assessment_period.model_dump(mode="json"),
                                   "source": doc.header.assessment_period_source}
                                  for i, doc in enumerate(documents) if doc.header.assessment_period]),
            DocumentSignal(name="taxes_from_content", provenance=SignalProvenance.CONTENT, confidence=confidence,
                           value=sorted({row.tax for doc in documents for row in doc.revenues})),
        )
        result = ParserExtraction(document_family="DARF", extraction_status=ExtractionStatus.MATCHED,
                                  confidence=confidence, signals=signals, warnings=warnings,
                                  structured_data=envelope.model_dump(mode="json"))
        # Reserve space for runtime context and the existing 64 KiB M2M ceiling.
        if len(json.dumps(result.model_dump(mode="json"), ensure_ascii=True).encode()) > 60_000:
            return _empty(ExtractionStatus.INCONCLUSIVE, "DARF_METADATA_LIMIT")
        return result


def _confidence(doc: DarfDocument) -> float:
    header = doc.header
    complete_period = header.assessment_period and header.assessment_period.kind != "UNKNOWN"
    complete_rows = bool(doc.revenues) and all(all(value is not None for value in (
        row.principal_amount, row.penalty_amount, row.interest_amount, row.total_amount,
    )) and row.tax != "UNKNOWN" for row in doc.revenues)
    checks = (header.taxpayer_id_structure_valid, header.taxpayer_name, complete_period, header.due_date,
              header.document_number, header.pay_until, header.total_amount is not None,
              complete_rows, doc.validation.sum_matches_total is True)
    return round(0.37 + sum(bool(check) for check in checks) * 0.07, 2)


def _empty(status: ExtractionStatus, warning: str) -> ParserExtraction:
    return ParserExtraction(document_family="UNKNOWN", extraction_status=status, warnings=(warning,))
