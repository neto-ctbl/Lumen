"""Content-first municipal ISS guide parsing for corpus-proven DUAM layouts."""

from __future__ import annotations

from decimal import Decimal
import json
import re

from pydantic import BaseModel, ConfigDict, Field
from unidecode import unidecode

from agent.parsers.contracts import (
    DocumentContext,
    DocumentSignal,
    ExtractionStatus,
    ParserExtraction,
    SignalProvenance,
    TechnicalFormat,
)
from agent.parsers.federal_revenue_guide import GuidePeriod, parse_guide_period
from agent.parsers.guide_common import (
    CNPJ_RE,
    CPF_RE,
    MONEY_RE,
    digits,
    parse_date,
    parse_money,
    read_pdf_pages,
    search_text,
    valid_cnpj,
    valid_cpf,
)
from agent.parsers.layout_framework import (
    ClassificationResult,
    ComposableDocumentParser,
    LayoutExtractionFailure,
    UNKNOWN_LAYOUT_ID,
)

ISS_PARSER_NAME = "lumen.iss-guide-pdf"
ISS_PARSER_VERSION = "1"
ANAPOLIS_DUAM_LAYOUT_ID = "ANAPOLIS_DUAM"
NEROPOLIS_DUAM_LAYOUT_ID = "NEROPOLIS_DUAM"

_ANAPOLIS_MARKERS = (
    "PREFEITURA MUNICIPAL DE ANAPOLIS",
    "DOCUMENTO UNICO DE ARRECADACAO MUNICIPAL",
    "DIRETORIA DA RECEITA",
    "GERENCIA DE FISCALIZACAO",
    "NOME DO PAGADOR",
    "INSCRICAO MUNICIPAL",
    "VALOR",
    "PRINCIPAL",
    "CORRECAO",
    "JUROS",
    "MULTA",
)
_NEROPOLIS_MARKERS = (
    "PREFEITURA MUNICIPAL DE NEROPOLIS",
    "DOCUMENTO UNICO DE ARRECADACAO MUNICIPAL",
    "SECRETARIA DE FINANCAS E ADMINISTRACAO",
    "REFERENCIA",
    "PARCELA",
    "VALOR ORIGINAL",
    "ATUALIZACAO",
    "DESCONTO",
)
_EXCLUDED_DOCUMENT = re.compile(
    r"\b(?:PARCELAMENTO|ACORDO DE PARCELAMENTO|CARTA DE LEMBRETE DE DEBITOS|"
    r"PERT|RELP|PARCSN|SISPAR)\b"
)
_ANAPOLIS_ROW = re.compile(
    rf"^\s*(?P<due>\d{{2}}/\d{{2}}/\d{{4}})\s+(?P<launch>\d+)\s+"
    rf"(?P<description>.+?)\s+(?P<principal>{MONEY_RE.pattern})\s+"
    rf"(?P<correction>{MONEY_RE.pattern})\s+(?P<interest>{MONEY_RE.pattern})\s+"
    rf"(?P<penalty>{MONEY_RE.pattern})\s+(?P<total>{MONEY_RE.pattern})\s*$",
    re.IGNORECASE,
)


class IssModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class IssGuideHeader(IssModel):
    layout: str
    taxpayer_id: str | None = None
    taxpayer_id_kind: str | None = None
    taxpayer_id_structure_valid: bool | None = None
    municipal_registration: str | None = None
    taxpayer_name: str | None = None
    municipality: str | None = None
    uf: str | None = None
    reference_label: str | None = None
    reference_period: GuidePeriod | None = None
    reference_period_source: str | None = None
    issue_date: str | None = None
    due_date: str | None = None
    pay_until: str | None = None
    document_number: str | None = None
    municipal_identifier: str | None = None
    total_amount: Decimal | None = None


class IssComponent(IssModel):
    code: str | None = None
    label: str
    kind: str
    amount: Decimal


class IssRevenue(IssModel):
    revenue_code: str | None = None
    description: str
    municipal_launch_id: str | None = None
    reference_label: str | None = None
    reference_period: GuidePeriod | None = None
    reference_period_source: str | None = None
    due_date: str | None = None
    tax_base: Decimal | None = None
    rate: Decimal | None = None
    components: tuple[IssComponent, ...] = ()
    principal_amount: Decimal | None = None
    correction_amount: Decimal | None = None
    penalty_amount: Decimal | None = None
    interest_amount: Decimal | None = None
    discount_amount: Decimal | None = None
    total_amount: Decimal | None = None


class IssGuideValidation(IssModel):
    calculated_total_amount: Decimal | None = None
    sum_matches_total: bool | None = None


class ExtractedIssGuideDocument(IssModel):
    header: IssGuideHeader
    revenues: tuple[IssRevenue, ...]
    validation: IssGuideValidation
    page_numbers: tuple[int, ...]
    block_numbers: tuple[int, ...]
    warning_codes: tuple[str, ...] = ()


class IssLayoutExtraction(IssModel):
    documents: tuple[ExtractedIssGuideDocument, ...]


class IssDocumentClassification(IssModel):
    classification: str
    classification_known: bool
    confidence: float | None = Field(default=None, ge=0, le=1)
    source: str | None = None


class IssClassificationResult(ClassificationResult):
    documents: tuple[IssDocumentClassification, ...]


class IssGuideDocument(IssModel):
    header: IssGuideHeader
    classification: IssDocumentClassification
    revenues: tuple[IssRevenue, ...]
    validation: IssGuideValidation
    page_numbers: tuple[int, ...]
    block_numbers: tuple[int, ...]
    warning_codes: tuple[str, ...] = ()


class IssGuideFile(IssModel):
    documents: tuple[IssGuideDocument, ...]


def has_anapolis_duam_layout(text: str) -> bool:
    normalized = search_text(text)
    return all(marker in normalized for marker in _ANAPOLIS_MARKERS) and all(
        marker in normalized for marker in ("DATA DE VENCIMENTO", "DESCRICAO", "TOTAL")
    )


def has_neropolis_duam_layout(text: str) -> bool:
    normalized = search_text(text)
    return all(marker in normalized for marker in _NEROPOLIS_MARKERS) and all(
        marker in normalized for marker in ("TRIBUTO", "VENCIMENTO", "VALIDADE ATE", "TOTAL")
    )


class AnapolisDuamExtractor:
    layout_id = ANAPOLIS_DUAM_LAYOUT_ID

    def supports_layout(self, context: DocumentContext) -> bool:
        pages = _matched_pdf_pages(context)
        return bool(pages) and all(has_anapolis_duam_layout(page) for page in pages)

    def extract(self, context: DocumentContext) -> IssLayoutExtraction:
        pages = _required_pdf_pages(context)
        if not pages or not all(has_anapolis_duam_layout(page) for page in pages):
            raise LayoutExtractionFailure(ExtractionStatus.UNSUPPORTED, "UNKNOWN_GUIDE_LAYOUT")
        return IssLayoutExtraction(
            documents=tuple(_extract_anapolis(page, number) for number, page in enumerate(pages, 1))
        )


class NeropolisDuamExtractor:
    layout_id = NEROPOLIS_DUAM_LAYOUT_ID

    def supports_layout(self, context: DocumentContext) -> bool:
        pages = _matched_pdf_pages(context)
        return bool(pages) and all(has_neropolis_duam_layout(page) for page in pages)

    def extract(self, context: DocumentContext) -> IssLayoutExtraction:
        pages = _required_pdf_pages(context)
        if not pages or not all(has_neropolis_duam_layout(page) for page in pages):
            raise LayoutExtractionFailure(ExtractionStatus.UNSUPPORTED, "UNKNOWN_GUIDE_LAYOUT")
        return IssLayoutExtraction(
            documents=tuple(_extract_neropolis(page, number) for number, page in enumerate(pages, 1))
        )


class IssGuideClassifier:
    """Classify extracted municipal rows; never reopens the source document."""

    def classify(
        self,
        extracted: IssLayoutExtraction,
        context: DocumentContext,
    ) -> IssClassificationResult:
        del context
        classified: list[IssDocumentClassification] = []
        warnings: list[str] = []
        for document in extracted.documents:
            descriptions = search_text(" ".join(row.description for row in document.revenues))
            own = bool(re.search(r"\bISSQN?\b.{0,35}\b(?:PROPRIO|PREST\.?\s+SERV\.?\s+PROPRIO)\b", descriptions))
            withheld = bool(re.search(r"\bISSQN?\b.{0,35}\b(?:RETIDO|RETENCAO|TOMADO)\b", descriptions))
            if own and not withheld:
                item = IssDocumentClassification(
                    classification="ISS_OWN", classification_known=True,
                    confidence=1, source="CONTENT_DESCRIPTION",
                )
            elif withheld and not own:
                item = IssDocumentClassification(
                    classification="ISS_WITHHELD", classification_known=True,
                    confidence=1, source="CONTENT_DESCRIPTION",
                )
            else:
                item = IssDocumentClassification(
                    classification="UNKNOWN", classification_known=False,
                    confidence=None, source=None,
                )
                warnings.append("ISS_MODALITY_INCONCLUSIVE")
            for row in document.revenues:
                if row.revenue_code and row.revenue_code not in {"002"}:
                    warnings.append("ISS_MUNICIPAL_REVENUE_CODE_UNKNOWN")
            classified.append(item)
            warnings.extend(document.warning_codes)
        ids = {item.classification for item in classified}
        classification_id = next(iter(ids)) if len(ids) == 1 else "UNKNOWN"
        known = len(ids) == 1 and classification_id != "UNKNOWN"
        if len(ids) > 1:
            warnings.append("ISS_MULTIPLE_MODALITIES")
        periods: list[dict[str, object]] = []
        observed_periods: set[tuple[str, str | None]] = set()
        for document in extracted.documents:
            candidates = []
            if document.header.reference_period is not None:
                candidates.append((document.header.reference_period, document.header.reference_period_source))
            candidates.extend(
                (revenue.reference_period, revenue.reference_period_source)
                for revenue in document.revenues
                if revenue.reference_period is not None
            )
            for period, source in candidates:
                key = (period.model_dump_json(), source)
                if key in observed_periods:
                    continue
                observed_periods.add(key)
                periods.append({"period": period.model_dump(mode="json"), "source": source})
        signals = (
            DocumentSignal(
                name="period_from_content",
                value=periods,
                provenance=SignalProvenance.CONTENT,
                confidence=1,
            ),
        ) if periods else ()
        return IssClassificationResult(
            classification_id=classification_id,
            classification_known=known,
            document_family="ISS_GUIDE",
            document_kind=classification_id,
            confidence=1 if known else None,
            signals=signals,
            warnings=tuple(dict.fromkeys(warnings)),
            documents=tuple(classified),
        )


class IssGuidePdfParser:
    name = ISS_PARSER_NAME
    version = ISS_PARSER_VERSION
    supported_formats = frozenset({TechnicalFormat.PDF})

    def __init__(self) -> None:
        self._pipelines = tuple(
            ComposableDocumentParser(
                name=self.name,
                version=self.version,
                supported_formats=self.supported_formats,
                extractor=extractor,
                classifier=IssGuideClassifier(),
                serialize_extracted=lambda extracted: _json_dict(extracted),
                serialize_result=_serialize_iss_result,
            )
            for extractor in (AnapolisDuamExtractor(), NeropolisDuamExtractor())
        )

    def supports(self, document: DocumentContext) -> bool:
        if document.technical_format is not TechnicalFormat.PDF:
            return False
        pages = _matched_pdf_pages(document)
        if not pages:
            return False
        combined = "\n".join(pages)
        if _excluded_document(combined):
            return _known_or_municipal_scope(combined)
        return any(pipeline.supports(document) for pipeline in self._pipelines) or _municipal_scope(combined)

    def parse(self, document: DocumentContext) -> ParserExtraction:
        if document.technical_format is not TechnicalFormat.PDF:
            return _empty(ExtractionStatus.UNSUPPORTED, "ISS_FORMAT_UNSUPPORTED")
        pages = _required_pdf_pages_result(document)
        if isinstance(pages, ParserExtraction):
            return pages
        combined = "\n".join(pages)
        if _excluded_document(combined):
            return _empty(ExtractionStatus.UNSUPPORTED, "ISS_INSTALLMENT_OR_COLLECTION_EXCLUDED")
        for pipeline in self._pipelines:
            if pipeline.supports(document):
                return pipeline.parse(document)
        return _empty(ExtractionStatus.UNSUPPORTED, "UNKNOWN_GUIDE_LAYOUT")


def _serialize_iss_result(
    extracted: IssLayoutExtraction,
    classification: ClassificationResult,
) -> dict[str, object]:
    classified = IssClassificationResult.model_validate(classification)
    documents = tuple(
        IssGuideDocument(
            header=document.header,
            classification=item,
            revenues=document.revenues,
            validation=document.validation,
            page_numbers=document.page_numbers,
            block_numbers=document.block_numbers,
            warning_codes=document.warning_codes,
        )
        for document, item in zip(extracted.documents, classified.documents, strict=True)
    )
    return _json_dict(IssGuideFile(documents=documents))


def _json_dict(model: BaseModel) -> dict[str, object]:
    return json.loads(model.model_dump_json())


def _extract_anapolis(text: str, page_number: int) -> ExtractedIssGuideDocument:
    lines = [line for line in text.splitlines() if line.strip()]
    warnings: list[str] = []
    rows: list[IssRevenue] = []
    due_from_row: str | None = None
    for index, line in enumerate(lines):
        match = _ANAPOLIS_ROW.match(line)
        if not match:
            continue
        due_from_row = parse_date(match["due"])
        description = " ".join(match["description"].split())
        if index + 1 < len(lines):
            continuation = search_text(lines[index + 1])
            if continuation in {"PROPRIO", "RETIDO", "TOMADO"}:
                description = f"{description} {' '.join(lines[index + 1].split())}"
        reference, reference_period = _period_from_description(description)
        values = {key: parse_money(match[key]) for key in ("principal", "correction", "interest", "penalty", "total")}
        components = (
            IssComponent(label="Valor Principal", kind="PRINCIPAL", amount=values["principal"]),
            IssComponent(label="Correção", kind="CORRECTION", amount=values["correction"]),
            IssComponent(label="Juros", kind="INTEREST", amount=values["interest"]),
            IssComponent(label="Multa", kind="PENALTY", amount=values["penalty"]),
        )
        rows.append(IssRevenue(
            description=description,
            municipal_launch_id=match["launch"],
            reference_label=reference,
            reference_period=reference_period,
            reference_period_source="CONTENT_DESCRIPTION" if reference_period else None,
            due_date=due_from_row,
            components=components,
            principal_amount=values["principal"], correction_amount=values["correction"],
            interest_amount=values["interest"], penalty_amount=values["penalty"],
            total_amount=values["total"],
        ))
    if not rows:
        warnings.append("ISS_REVENUES_MISSING")
    taxpayer = _field_value(lines, "CPF/CNPJ")
    taxpayer_id, taxpayer_kind, taxpayer_valid = _taxpayer_identity(taxpayer)
    if taxpayer_id is None:
        warnings.append("ISS_TAXPAYER_ID_MISSING")
    elif taxpayer_valid is False:
        warnings.append("ISS_TAXPAYER_ID_INVALID")
    observed = {
        (row.reference_label, row.reference_period.model_dump_json())
        for row in rows
        if row.reference_label and row.reference_period
    }
    if len(observed) == 1:
        period_row = next(row for row in rows if row.reference_label and row.reference_period)
        reference = period_row.reference_label
        period = period_row.reference_period
    else:
        reference = None
        period = None
    if not observed:
        warnings.append("ISS_REFERENCE_MISSING")
    elif len(observed) > 1:
        warnings.append("ISS_MULTIPLE_REFERENCE_PERIODS")
    total = sum((row.total_amount or Decimal("0") for row in rows), Decimal("0")) if rows else None
    calculated = sum((_calculated_revenue_total(row) for row in rows), Decimal("0")) if rows else None
    matches = calculated == total if calculated is not None and total is not None else None
    if matches is False:
        warnings.append("ISS_COMPONENT_TOTAL_MISMATCH")
    header = IssGuideHeader(
        layout=ANAPOLIS_DUAM_LAYOUT_ID,
        taxpayer_id=taxpayer_id, taxpayer_id_kind=taxpayer_kind,
        taxpayer_id_structure_valid=taxpayer_valid,
        municipal_registration=_field_value(lines, "INSCRICAO MUNICIPAL"),
        taxpayer_name=_field_value(lines, "NOME DO PAGADOR"),
        municipality="ANAPOLIS", uf="GO",
        reference_label=reference, reference_period=period,
        reference_period_source="CONTENT_DESCRIPTION" if period else None,
        issue_date=_labeled_date(lines, "DATA EMISSAO"),
        due_date=_labeled_date(lines, "VENCIMENTO") or due_from_row,
        document_number=_labeled_digits(lines, ("NR. DA GUIA", "N DA GUIA", "NO DA GUIA")),
        municipal_identifier=_labeled_digits(lines, ("NOSSO NUMERO",)),
        total_amount=total,
    )
    if header.document_number is None:
        warnings.append("ISS_DOCUMENT_NUMBER_MISSING")
    if header.due_date is None:
        warnings.append("ISS_DUE_DATE_MISSING_OR_INVALID")
    return ExtractedIssGuideDocument(
        header=header, revenues=tuple(rows),
        validation=IssGuideValidation(calculated_total_amount=calculated, sum_matches_total=matches),
        page_numbers=(page_number,), block_numbers=(1,),
        warning_codes=tuple(dict.fromkeys(warnings)),
    )


def _extract_neropolis(text: str, page_number: int) -> ExtractedIssGuideDocument:
    lines = [line for line in text.splitlines() if line.strip()]
    warnings: list[str] = []
    rows: list[IssRevenue] = []
    for line in lines:
        row = re.match(r"^\s*(?P<code>\d{3,8})\s*-\s*(?P<body>ISSQN?.*)$", line, re.IGNORECASE)
        if not row:
            continue
        money = list(MONEY_RE.finditer(row["body"]))
        if len(money) < 6:
            continue
        description = row["body"][:money[0].start()].strip()
        values = [parse_money(item[0]) for item in money]
        principal, correction, penalty, interest, discount, total = values[-6:]
        rate_match = re.search(r"(?<!\d)(\d+(?:[.,]\d+)?)\s*%", row["body"])
        components = (
            IssComponent(label="Valor Original", kind="PRINCIPAL", amount=principal),
            IssComponent(label="Atualização", kind="CORRECTION", amount=correction),
            IssComponent(label="Multa", kind="PENALTY", amount=penalty),
            IssComponent(label="Juros", kind="INTEREST", amount=interest),
            IssComponent(label="Desconto", kind="DISCOUNT", amount=discount),
        )
        rows.append(IssRevenue(
            revenue_code=row["code"], description=" ".join(description.split()),
            tax_base=values[-7] if len(values) >= 7 else None,
            rate=Decimal(rate_match[1].replace(",", ".")) if rate_match else None,
            components=components,
            principal_amount=principal, correction_amount=correction,
            penalty_amount=penalty, interest_amount=interest,
            discount_amount=discount, total_amount=total,
        ))
    if not rows:
        warnings.append("ISS_REVENUES_MISSING")
    taxpayer = _field_value(lines, "CNPJ/CPF") or _field_value(lines, "CNPJ") or _field_value(lines, "CPF")
    taxpayer_id, taxpayer_kind, taxpayer_valid = _taxpayer_identity(taxpayer)
    if taxpayer_id is None:
        warnings.append("ISS_TAXPAYER_ID_MISSING")
    elif taxpayer_valid is False:
        warnings.append("ISS_TAXPAYER_ID_INVALID")
    reference = _field_value(lines, "REFERENCIA")
    period = parse_guide_period(reference)
    if period is None:
        warnings.append("ISS_REFERENCE_MISSING")
    elif period.kind == "UNKNOWN":
        warnings.append("ISS_REFERENCE_UNINTERPRETED")
    if period is not None:
        rows = [
            row.model_copy(update={
                "reference_label": reference,
                "reference_period": period,
                "reference_period_source": "CONTENT_REFERENCE",
            })
            for row in rows
        ]
    total = sum((row.total_amount or Decimal("0") for row in rows), Decimal("0")) if rows else None
    calculated = sum((_calculated_revenue_total(row) for row in rows), Decimal("0")) if rows else None
    matches = calculated == total if calculated is not None and total is not None else None
    if matches is False:
        warnings.append("ISS_COMPONENT_TOTAL_MISMATCH")
    header = IssGuideHeader(
        layout=NEROPOLIS_DUAM_LAYOUT_ID,
        taxpayer_id=taxpayer_id, taxpayer_id_kind=taxpayer_kind,
        taxpayer_id_structure_valid=taxpayer_valid,
        municipal_registration=_field_value(lines, "INSCRICAO MUNICIPAL"),
        taxpayer_name=_field_value(lines, "CONTRIBUINTE"),
        municipality="NEROPOLIS", uf="GO",
        reference_label=reference, reference_period=period,
        reference_period_source="CONTENT_REFERENCE" if period else None,
        issue_date=_labeled_date(lines, "EMISSAO"),
        due_date=_labeled_date(lines, "VENCIMENTO"),
        pay_until=_labeled_date(lines, "VALIDADE ATE"),
        document_number=_labeled_digits(lines, ("DUAM",)) or _field_digits(lines, "DUAM"),
        municipal_identifier=_labeled_digits(lines, ("NOSSO NUMERO",)),
        total_amount=total,
    )
    if header.document_number is None:
        warnings.append("ISS_DOCUMENT_NUMBER_MISSING")
    if header.due_date is None:
        warnings.append("ISS_DUE_DATE_MISSING_OR_INVALID")
    return ExtractedIssGuideDocument(
        header=header, revenues=tuple(rows),
        validation=IssGuideValidation(calculated_total_amount=calculated, sum_matches_total=matches),
        page_numbers=(page_number,), block_numbers=(1,),
        warning_codes=tuple(dict.fromkeys(warnings)),
    )


def _field_value(lines: list[str], label: str) -> str | None:
    labels = (
        "NOME DO PAGADOR", "CONTRIBUINTE", "INSCRICAO MUNICIPAL", "CPF/CNPJ", "CNPJ", "CPF",
        "REFERENCIA", "PARCELA", "EMISSAO", "CONVENIO", "VENCIMENTO", "VALIDADE ATE", "DUAM",
    )
    for index, line in enumerate(lines):
        normalized = unidecode(line).upper()
        match = re.search(rf"(?<![A-Z]){re.escape(label)}(?![A-Z])", normalized)
        if not match:
            continue
        later = [found.start() for other in labels if other != label
                 for found in re.finditer(rf"(?<![A-Z]){re.escape(other)}(?![A-Z])", normalized)
                 if found.start() >= match.end()]
        end = min(later, default=len(line))
        inline = line[match.end():end].strip(" :")
        if inline and inline != "-":
            return inline
        if index + 1 < len(lines):
            cell = lines[index + 1][match.start():end if later else None].strip(" :")
            if cell and cell != "-":
                return cell
    return None


def _labeled_date(lines: list[str], label: str) -> str | None:
    for line in lines:
        normalized = unidecode(line).upper()
        position = normalized.find(label)
        if position >= 0:
            match = re.search(r"\d{2}/\d{2}/\d{4}", line[position + len(label):])
            if match and parse_date(match[0]):
                return parse_date(match[0])
    value = _field_value(lines, label)
    match = re.search(r"\d{2}/\d{2}/\d{4}", value or "")
    return parse_date(match[0]) if match else None


def _labeled_digits(lines: list[str], labels: tuple[str, ...]) -> str | None:
    for line in lines:
        normalized = unidecode(line).upper()
        for label in labels:
            position = normalized.find(label)
            if position < 0:
                continue
            match = re.search(r"\b\d{5,30}\b", line[position + len(label):])
            if match:
                return match[0]
    return None


def _field_digits(lines: list[str], label: str) -> str | None:
    match = re.search(r"\b\d{5,30}\b", _field_value(lines, label) or "")
    return match[0] if match else None


def _taxpayer_identity(value: str | None) -> tuple[str | None, str | None, bool | None]:
    cnpj = CNPJ_RE.search(value or "")
    cpf = CPF_RE.search(value or "")
    if cnpj:
        identifier = digits(cnpj[0])
        return identifier, "CNPJ", valid_cnpj(identifier)
    if cpf:
        identifier = digits(cpf[0])
        return identifier, "CPF", valid_cpf(identifier)
    identifier = digits(value or "")
    if len(identifier) == 14:
        return identifier, "CNPJ", valid_cnpj(identifier)
    if len(identifier) == 11:
        return identifier, "CPF", valid_cpf(identifier)
    return None, None, None


def _period_from_description(description: str) -> tuple[str | None, GuidePeriod | None]:
    match = re.search(
        r"\b(?:REF\.?\s*A\s*)?(0?[1-9]|1[0-2])/(\d{4})\b",
        search_text(description),
    )
    label = f"{match[1]}/{match[2]}" if match else None
    return label, parse_guide_period(label)


def _calculated_revenue_total(row: IssRevenue) -> Decimal:
    return (
        (row.principal_amount or Decimal("0"))
        + (row.correction_amount or Decimal("0"))
        + (row.penalty_amount or Decimal("0"))
        + (row.interest_amount or Decimal("0"))
        - (row.discount_amount or Decimal("0"))
    )


def _excluded_document(text: str) -> bool:
    return bool(_EXCLUDED_DOCUMENT.search(search_text(text)))


def _municipal_scope(text: str) -> bool:
    normalized = search_text(text)
    return (
        "PREFEITURA" in normalized
        and "DOCUMENTO" in normalized
        and "ARRECADACAO MUNICIPAL" in normalized
        and "ISS" in normalized
    )


def _known_or_municipal_scope(text: str) -> bool:
    return has_anapolis_duam_layout(text) or has_neropolis_duam_layout(text) or _municipal_scope(text)


def _matched_pdf_pages(context: DocumentContext) -> tuple[str, ...]:
    if context.technical_format is not TechnicalFormat.PDF:
        return ()
    pages = read_pdf_pages(context.file_path)
    return pages.pages if pages.status is ExtractionStatus.MATCHED else ()


def _required_pdf_pages(context: DocumentContext) -> tuple[str, ...]:
    result = _required_pdf_pages_result(context)
    if isinstance(result, ParserExtraction):
        warning = result.warnings[0]
        raise LayoutExtractionFailure(result.extraction_status, warning)
    return result


def _required_pdf_pages_result(context: DocumentContext) -> tuple[str, ...] | ParserExtraction:
    pages = read_pdf_pages(context.file_path)
    if pages.status is ExtractionStatus.INVALID:
        return _empty(ExtractionStatus.INVALID, "INVALID_PDF")
    if pages.status is ExtractionStatus.INCONCLUSIVE:
        return _empty(ExtractionStatus.INCONCLUSIVE, "PDF_TEXT_LAYER_MISSING")
    return pages.pages


def _empty(status: ExtractionStatus, warning: str) -> ParserExtraction:
    return ParserExtraction(
        document_family="UNKNOWN",
        extraction_status=status,
        signals=(DocumentSignal(
            name="layout_id", value=UNKNOWN_LAYOUT_ID,
            provenance=SignalProvenance.FILE_STRUCTURE, confidence=None,
        ),),
        warnings=(warning,),
    )
