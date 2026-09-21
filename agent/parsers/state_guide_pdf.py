"""Content-first normal state-guide classifier; installments remain unsupported."""

from __future__ import annotations

import json
import re

from agent.parsers.contracts import (
    DocumentContext, DocumentSignal, ExtractionStatus, ParserExtraction,
    SignalProvenance, TechnicalFormat,
)
from agent.parsers.guide_common import read_pdf_pages, search_text
from agent.parsers.state_revenue_codes import classify_state_revenue
from agent.parsers.state_revenue_guide import (
    StateGuideHeader, StateGuideValidation, StateModel, StateRevenue,
    StateRevenueGuideExtractor, field_value, has_go_dare_51_layout,
)

STATE_PARSER_NAME = "lumen.state-guide-pdf"
STATE_PARSER_VERSION = "1"
_EXCLUDED = re.compile(r"\b(?:PARCELAMENTO|PARCELAMENTOS|PARCELAS|ACORDO|PGFN|SISPAR|PARCSN|PERT|RELP|SIMEI|PREFEITURA|ISSQN|ISS)\b")


class StateGuideDocument(StateModel):
    header: StateGuideHeader
    guide_kind: str
    revenues: tuple[StateRevenue, ...]
    validation: StateGuideValidation
    page_numbers: tuple[int, ...]
    block_numbers: tuple[int, ...]
    warning_codes: tuple[str, ...] = ()


class StateGuideFile(StateModel):
    documents: tuple[StateGuideDocument, ...]


def _signature(text: str) -> bool:
    return has_go_dare_51_layout(text)


def _excluded(text: str) -> bool:
    norm = search_text(text)
    # The normal DARE shell itself contains a blank Parcela field.
    explicit_parcela = any(re.search(r"\bPARCELA\s*[:#-]?\s*\d+", search_text(line))
                           for line in text.splitlines())
    return bool(_EXCLUDED.search(norm) or explicit_parcela or field_value(text.splitlines(), "PARCELA"))


def go_dare_51_layout_blocks(pages: tuple[str, ...]) -> tuple[tuple[int, int, str], ...] | None:
    """Split complete DARE 5.1 pages without applying fiscal exclusions."""
    blocks = []
    for page_number, page in enumerate(pages, 1):
        lines = [line for line in page.splitlines() if line.strip()]
        starts = [i for i, line in enumerate(lines)
                  if "DOCUMENTO DE ARRECADACAO DE RECEITAS ESTADUAIS" in search_text(line)]
        page_blocks = []
        # Require the whole page to be normal-state compatible too, so a marker
        # in a bank copy or footer cannot disappear when selecting detailed copies.
        if not _signature(page):
            return None
        for block, start in enumerate(starts, 1):
            end = starts[block] if block < len(starts) else len(lines)
            candidate = "\n".join(lines[max(0, start - 3):end])
            if any(re.match(r"^\s*RECEITA\b", search_text(line)) for line in candidate.splitlines()):
                if not _signature(candidate):
                    return None
                page_blocks.append((page_number, block, candidate))
            else:
                # Only a documented bank copy is ignorable, not an incomplete
                # independent guide. Its explicit number must match a detail copy.
                norm = search_text(candidate)
                number = re.search(r"\bN[O°º]?\s*[.:]?\s*(\d{5,30})\b", norm)
                other_numbers = [re.search(r"\bN[O°º]?\s*[.:]?\s*(\d{5,30})\b", search_text(line))
                                 for line in lines[end:]]
                if not (number and any(other and other[1] == number[1] for other in other_numbers)
                        and "TOTAL A RECOLHER" in norm and "VALIDADE DO" in norm):
                    return None
        if not page_blocks:
            return None
        blocks.extend(page_blocks)
    return tuple(blocks)


def _blocks(pages: tuple[str, ...]) -> tuple[tuple[int, int, str], ...] | None:
    # Classification exclusions remain outside physical layout recognition.
    if any(_excluded(page) for page in pages):
        return None
    return go_dare_51_layout_blocks(pages)


class StateGuidePdfParser:
    name = STATE_PARSER_NAME
    version = STATE_PARSER_VERSION
    supported_formats = frozenset({TechnicalFormat.PDF})

    def supports(self, document: DocumentContext) -> bool:
        if document.technical_format is not TechnicalFormat.PDF:
            return False
        pages = read_pdf_pages(document.file_path)
        return pages.status is ExtractionStatus.MATCHED and bool(_blocks(pages.pages))

    def parse(self, document: DocumentContext) -> ParserExtraction:
        if document.technical_format is not TechnicalFormat.PDF:
            return _empty(ExtractionStatus.UNSUPPORTED, "STATE_FORMAT_UNSUPPORTED")
        pages = read_pdf_pages(document.file_path)
        if pages.status is ExtractionStatus.INVALID:
            return _empty(ExtractionStatus.INVALID, "INVALID_PDF")
        if pages.status is ExtractionStatus.INCONCLUSIVE:
            return _empty(ExtractionStatus.INCONCLUSIVE, "PDF_TEXT_LAYER_MISSING")
        blocks = _blocks(pages.pages)
        if not blocks:
            return _empty(ExtractionStatus.UNSUPPORTED, "STATE_SIGNATURE_NOT_FOUND_OR_EXCLUDED")
        if len(blocks) > 64:
            return _empty(ExtractionStatus.INCONCLUSIVE, "STATE_DOCUMENT_LIMIT")
        try:
            return self._parse_blocks(blocks)
        except Exception:
            return _empty(ExtractionStatus.ERROR, "STATE_EXTRACTION_ERROR")

    def _parse_blocks(self, blocks: tuple[tuple[int, int, str], ...]) -> ParserExtraction:
        documents = []
        for page, block, text in blocks:
            extracted = StateRevenueGuideExtractor().extract(text)
            warnings = [f"STATE_{code}" for code in extracted.warning_codes]
            rows = []
            for row in extracted.revenues:
                tax, kind, source, codes = classify_state_revenue(
                    row.revenue_code, row.description, row.parent_revenue_code, row.parent_description,
                )
                rows.append(row.model_copy(update={"tax": tax, "guide_kind": kind, "classification_source": source}))
                warnings.extend(codes)
            kinds = {row.guide_kind for row in rows}
            kind = next(iter(kinds)) if len(kinds) == 1 else "UNKNOWN"
            if len(kinds) > 1:
                warnings.append("STATE_MULTIPLE_GUIDE_KINDS")
            current = StateGuideDocument(
                header=extracted.header, guide_kind=kind, revenues=tuple(rows), validation=extracted.validation,
                page_numbers=(page,), block_numbers=(block,), warning_codes=tuple(dict.fromkeys(warnings)),
            )
            # Only exact repeats with explicit identity deduplicate. Unequal rows
            # are not guessed to be a continuation or a second independent guide.
            repeats = [i for i, old in enumerate(documents) if current.header.document_number
                       and current.header == old.header and current.revenues == old.revenues]
            if repeats:
                index = repeats[0]
                old = documents[index]
                documents[index] = old.model_copy(update={
                    "page_numbers": (*old.page_numbers, page), "block_numbers": (*old.block_numbers, block),
                    "warning_codes": tuple(dict.fromkeys((*old.warning_codes, "STATE_REPEATED_DOCUMENT_BLOCK"))),
                })
            else:
                if any(current.header.document_number and old.header.document_number == current.header.document_number
                       for old in documents):
                    current = current.model_copy(update={"warning_codes": (*current.warning_codes, "STATE_DOCUMENT_NUMBER_CONFLICT")})
                documents.append(current)
        warnings = tuple(dict.fromkeys(code for doc in documents for code in doc.warning_codes))
        confidence = min(_confidence(doc) for doc in documents)
        signals = (
            DocumentSignal(name="period_from_content", provenance=SignalProvenance.CONTENT, confidence=confidence,
                           value=[{"document_index": i, "period": doc.header.reference_period.model_dump(mode="json"),
                                   "source": doc.header.reference_period_source}
                                  for i, doc in enumerate(documents) if doc.header.reference_period]),
            DocumentSignal(name="state_guide_kinds_from_content", provenance=SignalProvenance.CONTENT,
                           confidence=confidence, value=sorted({doc.guide_kind for doc in documents})),
        )
        result = ParserExtraction(document_family="STATE_GUIDE", extraction_status=ExtractionStatus.MATCHED,
                                  confidence=confidence, signals=signals, warnings=warnings,
                                  structured_data=StateGuideFile(documents=tuple(documents)).model_dump(mode="json"))
        if len(json.dumps(result.model_dump(mode="json"), ensure_ascii=True).encode()) > 60_000:
            return _empty(ExtractionStatus.INCONCLUSIVE, "STATE_METADATA_LIMIT")
        return result


def _confidence(doc: StateGuideDocument) -> float:
    header = doc.header
    checks = (header.taxpayer_id_structure_valid, header.state_registration, header.taxpayer_name,
              header.document_number, header.reference_period and header.reference_period.kind != "UNKNOWN",
              header.due_date, header.total_amount is not None, doc.validation.sum_matches_total is True,
              doc.revenues and all(row.guide_kind != "UNKNOWN" and row.components and row.principal_amount is not None
                                   for row in doc.revenues))
    return round(0.37 + sum(bool(check) for check in checks) * 0.07, 2)


def _empty(status: ExtractionStatus, warning: str) -> ParserExtraction:
    return ParserExtraction(document_family="UNKNOWN", extraction_status=status, warnings=(warning,))
