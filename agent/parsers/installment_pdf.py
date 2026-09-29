"""Content-first parser for federal, Simples and Goiás installment guides."""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
import re

from pydantic import BaseModel, ConfigDict, Field

from agent.parsers.contracts import (
    DocumentContext,
    DocumentSignal,
    ExtractionStatus,
    ParserExtraction,
    SignalProvenance,
    TechnicalFormat,
)
from agent.parsers.darf_pdf import federal_revenue_form_blocks
from agent.parsers.das_pdf import DasDocument, extract_das_form, has_das_form_layout
from agent.parsers.federal_revenue_guide import (
    FederalRevenueGuide,
    FederalRevenueGuideExtractor,
    GuidePeriod,
    PeriodKind,
)
from agent.parsers.guide_common import read_pdf_pages, search_text
from agent.parsers.known_layouts import (
    DAS_FORM_LAYOUT_ID,
    FEDERAL_REVENUE_FORM_LAYOUT_ID,
    GO_DARE_51_LAYOUT_ID,
)
from agent.parsers.layout_framework import (
    ClassificationResult,
    ComposableDocumentParser,
    LayoutExtractionFailure,
    default_layout_registry,
)
from agent.parsers.legacy_darf import (
    LEGACY_DARF_FORM_LAYOUT_ID,
    LegacyDarfDocument,
    extract_legacy_darf_form,
    has_legacy_darf_form_layout,
    legacy_darf_form_blocks,
)
from agent.parsers.state_guide_pdf import go_dare_51_layout_blocks
from agent.parsers.state_revenue_guide import ExtractedStateGuide, StateRevenueGuideExtractor

INSTALLMENT_PARSER_NAME = "lumen.installment-pdf"
INSTALLMENT_PARSER_VERSION = "1"
_SIMPLIFIED_INSTALLMENT_REVENUE_CODE = "1124"
_INSTALLMENT_MARKER = re.compile(
    r"\b(?:PARCELAMENTO|PARCSN|PARCMEI|PGFN|SISPAR|PERTSN|PERT|RELPSN|RELP|SIMEI)\b"
)
_PROGRAM_MARKERS = (
    "PGFN-SISPAR",
    "PGFN",
    "SISPAR",
    "PARCSN",
    "PARCMEI",
    "SIMEI",
    "PERTSN",
    "PERT",
    "RELPSN",
    "RELP",
    "PARCELAMENTO",
)


class InstallmentProgram(str, Enum):
    PGFN = "PGFN"
    PARCSN = "PARCSN"
    PARCMEI = "PARCMEI"
    RELP = "RELP"
    PERT = "PERT"
    SIMPLIFICADO = "SIMPLIFICADO"
    SEFAZ = "SEFAZ"
    UNKNOWN = "UNKNOWN"


class InstallmentAdministrator(str, Enum):
    PGFN = "PGFN"
    SIMPLES_NACIONAL = "SIMPLES_NACIONAL"
    RFB = "RFB"
    SEFAZ_GO = "SEFAZ_GO"
    UNKNOWN = "UNKNOWN"


class InstallmentDebtScope(str, Enum):
    FEDERAL = "FEDERAL"
    SIMPLES_NACIONAL = "SIMPLES_NACIONAL"
    SIMEI = "SIMEI"
    STATE = "STATE"
    UNKNOWN = "UNKNOWN"


class InstallmentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class InstallmentHeader(InstallmentModel):
    layout: str
    page_number: int = Field(ge=1)
    block_number: int = Field(ge=1)
    taxpayer_id: str | None = None
    taxpayer_id_kind: str | None = None
    taxpayer_id_structure_valid: bool | None = None
    taxpayer_name: str | None = None


class InstallmentIdentity(InstallmentModel):
    installment_reference: str | None = None
    agreement_number: str | None = None
    registration_number: str | None = None
    current_installment: int | None = Field(default=None, ge=1)
    total_installments: int | None = Field(default=None, ge=1)
    reference_period: GuidePeriod | None = None
    document_number: str | None = None


class InstallmentDebt(InstallmentModel):
    scope: InstallmentDebtScope
    taxes: tuple[str, ...] = ()
    original_debt_periods: tuple[GuidePeriod, ...] = ()
    raw_debt_description: str | None = None


class InstallmentPayment(InstallmentModel):
    due_date: str | None = None
    pay_until: str | None = None
    principal_amount: Decimal | None = None
    penalty_amount: Decimal | None = None
    interest_amount: Decimal | None = None
    correction_amount: Decimal | None = None
    total_amount: Decimal | None = None


class InstallmentComponent(InstallmentModel):
    code: str | None = None
    description: str | None = None
    tax: str | None = None
    reference_period: GuidePeriod | None = None
    uf: str | None = None
    municipality: str | None = None
    principal_amount: Decimal | None = None
    penalty_amount: Decimal | None = None
    interest_amount: Decimal | None = None
    correction_amount: Decimal | None = None
    total_amount: Decimal | None = None


class InstallmentValidation(InstallmentModel):
    components_total_amount: Decimal | None = None
    sum_matches_total: bool | None = None
    pay_until_matches_due_date: bool | None = None


class InstallmentDocument(InstallmentModel):
    header: InstallmentHeader
    program: InstallmentProgram
    administrator: InstallmentAdministrator
    installment: InstallmentIdentity
    debt: InstallmentDebt
    payment: InstallmentPayment
    components: tuple[InstallmentComponent, ...]
    validation: InstallmentValidation
    warning_codes: tuple[str, ...] = ()


class InstallmentFile(InstallmentModel):
    documents: tuple[InstallmentDocument, ...]


class InstallmentDocumentDraft(InstallmentModel):
    header: InstallmentHeader
    installment: InstallmentIdentity
    payment: InstallmentPayment
    components: tuple[InstallmentComponent, ...]
    validation: InstallmentValidation
    semantic_markers: tuple[str, ...] = ()
    layout_revenue_codes: tuple[str, ...] = ()
    warning_codes: tuple[str, ...] = ()


class InstallmentLayoutExtraction(InstallmentModel):
    documents: tuple[InstallmentDocumentDraft, ...]


class InstallmentDocumentClassification(InstallmentModel):
    program: InstallmentProgram
    administrator: InstallmentAdministrator
    debt_scope: InstallmentDebtScope
    taxes: tuple[str, ...] = ()
    raw_debt_description: str | None = None
    confidence: float
    warning_codes: tuple[str, ...] = ()


class InstallmentClassificationResult(ClassificationResult):
    documents: tuple[InstallmentDocumentClassification, ...]


class _DasInstallmentExtractor:
    layout_id = DAS_FORM_LAYOUT_ID

    def supports_layout(self, context: DocumentContext) -> bool:
        pages = _pages(context)
        return bool(pages) and all(has_das_form_layout(page) for page in pages)

    def extract(self, context: DocumentContext) -> InstallmentLayoutExtraction:
        pages = _pages(context)
        drafts = tuple(
            _draft_from_das(extract_das_form(text).document, text, page_number)
            for page_number, text in enumerate(pages, start=1)
            if has_das_form_layout(text)
        )
        return _require_drafts(drafts)


class _FederalInstallmentExtractor:
    layout_id = FEDERAL_REVENUE_FORM_LAYOUT_ID

    def supports_layout(self, context: DocumentContext) -> bool:
        return bool(federal_revenue_form_blocks(_pages(context)))

    def extract(self, context: DocumentContext) -> InstallmentLayoutExtraction:
        extractor = FederalRevenueGuideExtractor()
        drafts = tuple(
            _draft_from_federal(extractor.extract(text), text, page, block)
            for page, block, text in federal_revenue_form_blocks(_pages(context))
        )
        return _require_drafts(drafts)


class _StateInstallmentExtractor:
    layout_id = GO_DARE_51_LAYOUT_ID

    def supports_layout(self, context: DocumentContext) -> bool:
        return bool(go_dare_51_layout_blocks(_pages(context)))

    def extract(self, context: DocumentContext) -> InstallmentLayoutExtraction:
        extractor = StateRevenueGuideExtractor()
        drafts = tuple(
            _draft_from_state(extractor.extract(text), text, page, block)
            for page, block, text in go_dare_51_layout_blocks(_pages(context))
        )
        return _require_drafts(drafts)


class _LegacyDarfInstallmentExtractor:
    layout_id = LEGACY_DARF_FORM_LAYOUT_ID

    def supports_layout(self, context: DocumentContext) -> bool:
        return any(has_legacy_darf_form_layout(page) for page in _pages(context))

    def extract(self, context: DocumentContext) -> InstallmentLayoutExtraction:
        drafts: list[InstallmentDocumentDraft] = []
        seen: set[tuple[object, ...]] = set()
        for page, text in enumerate(_pages(context), start=1):
            for block, content in enumerate(legacy_darf_form_blocks(text), start=1):
                document = extract_legacy_darf_form(content)
                draft = _draft_from_legacy(document, content, page, block)
                key = (
                    draft.header.taxpayer_id,
                    draft.installment.document_number,
                    draft.payment.total_amount,
                    draft.layout_revenue_codes,
                )
                if key not in seen:
                    drafts.append(draft)
                    seen.add(key)
        return _require_drafts(tuple(drafts))


class InstallmentClassifier:
    def classify(
        self,
        extracted: InstallmentLayoutExtraction,
        context: DocumentContext,
    ) -> InstallmentClassificationResult:
        del context
        classified = tuple(_classify_document(document) for document in extracted.documents)
        programs = {item.program for item in classified}
        known = all(program is not InstallmentProgram.UNKNOWN for program in programs)
        classification_id = next(iter(programs)).value if len(programs) == 1 else "MULTIPLE"
        confidence = min(item.confidence for item in classified)
        warnings = tuple(dict.fromkeys(code for item in classified for code in item.warning_codes))
        return InstallmentClassificationResult(
            classification_id=classification_id,
            classification_known=known,
            document_family="INSTALLMENT",
            document_kind=classification_id,
            confidence=confidence,
            signals=(
                DocumentSignal(
                    name="installment_program",
                    value=classification_id,
                    provenance=SignalProvenance.CONTENT,
                    confidence=confidence,
                ),
            ),
            warnings=warnings,
            documents=classified,
        )


class InstallmentPdfParser:
    name = INSTALLMENT_PARSER_NAME
    version = INSTALLMENT_PARSER_VERSION
    supported_formats = frozenset({TechnicalFormat.PDF})

    def __init__(self) -> None:
        classifier = InstallmentClassifier()
        self._pipelines = tuple(
            ComposableDocumentParser(
                name=self.name,
                version=self.version,
                supported_formats=self.supported_formats,
                extractor=extractor,
                classifier=classifier,
                serialize_extracted=lambda extracted: extracted.model_dump(mode="json"),
                serialize_result=_serialize_result,
            )
            for extractor in (
                _DasInstallmentExtractor(),
                _FederalInstallmentExtractor(),
                _StateInstallmentExtractor(),
                _LegacyDarfInstallmentExtractor(),
            )
        )
        self._pipelines_by_layout = {
            pipeline.extractor.layout_id: pipeline for pipeline in self._pipelines
        }

    def supports(self, document: DocumentContext) -> bool:
        if document.technical_format is not TechnicalFormat.PDF:
            return False
        pages = _pages(document)
        if not _has_installment_evidence(pages):
            return False
        identified = default_layout_registry().identify(document)
        pipeline = self._pipelines_by_layout.get(identified.layout_id)
        return pipeline.supports(document) if pipeline is not None else False

    def parse(self, document: DocumentContext) -> ParserExtraction:
        if document.technical_format is not TechnicalFormat.PDF:
            return _empty(ExtractionStatus.UNSUPPORTED, "INSTALLMENT_FORMAT_UNSUPPORTED")
        try:
            pages = _pages(document)
        except LayoutExtractionFailure as exc:
            return _empty(exc.status, exc.warning)
        if not _has_installment_evidence(pages):
            return _empty(ExtractionStatus.UNSUPPORTED, "INSTALLMENT_SIGNATURE_NOT_FOUND")
        identified = default_layout_registry().identify(document)
        pipeline = self._pipelines_by_layout.get(identified.layout_id)
        if pipeline is not None and pipeline.supports(document):
            return pipeline.parse(document)
        return _empty(ExtractionStatus.UNSUPPORTED, "UNKNOWN_INSTALLMENT_LAYOUT")


def _pages(context: DocumentContext) -> tuple[str, ...]:
    if context.technical_format is not TechnicalFormat.PDF:
        raise LayoutExtractionFailure(ExtractionStatus.UNSUPPORTED, "LAYOUT_FORMAT_UNSUPPORTED")
    pages = read_pdf_pages(context.file_path)
    if pages.status is ExtractionStatus.INVALID:
        raise LayoutExtractionFailure(ExtractionStatus.INVALID, "INVALID_PDF")
    if pages.status is ExtractionStatus.INCONCLUSIVE:
        raise LayoutExtractionFailure(ExtractionStatus.INCONCLUSIVE, "PDF_TEXT_LAYER_MISSING")
    return pages.pages


def _has_installment_evidence(pages: tuple[str, ...]) -> bool:
    normalized = search_text("\n".join(pages))
    return bool(_INSTALLMENT_MARKER.search(normalized)) or (
        any(has_legacy_darf_form_layout(page) for page in pages)
        and bool(re.search(r"\b1124\b", normalized))
    )


def _semantic_markers(text: str) -> tuple[str, ...]:
    normalized = search_text(text)
    return tuple(marker for marker in _PROGRAM_MARKERS if re.search(rf"\b{re.escape(marker)}\b", normalized))


def _draft_from_das(document: DasDocument, text: str, page: int) -> InstallmentDocumentDraft:
    installment = _installment_identity(
        text,
        reference_period=_month_period(document.header.assessment_period),
        document_number=document.header.document_number,
    )
    components = tuple(
        InstallmentComponent(
            code=item.code,
            description=item.denomination,
            tax=item.tax_family,
            reference_period=_month_period(item.assessment_period),
            uf=item.state,
            municipality=item.municipality,
            principal_amount=item.principal_amount,
            penalty_amount=item.penalty_amount,
            interest_amount=item.interest_amount,
            total_amount=item.total_amount,
        )
        for item in document.components
    )
    return InstallmentDocumentDraft(
        header=InstallmentHeader(
            layout=DAS_FORM_LAYOUT_ID,
            page_number=page,
            block_number=1,
            taxpayer_id=document.header.cnpj,
            taxpayer_id_kind="CNPJ" if document.header.cnpj else None,
            taxpayer_id_structure_valid=document.header.cnpj_structure_valid,
            taxpayer_name=document.header.corporate_name,
        ),
        installment=installment,
        payment=InstallmentPayment(
            due_date=document.header.due_date,
            pay_until=document.header.pay_until,
            principal_amount=_sum_amount(components, "principal_amount"),
            penalty_amount=_sum_amount(components, "penalty_amount"),
            interest_amount=_sum_amount(components, "interest_amount"),
            total_amount=document.header.total_amount,
        ),
        components=components,
        validation=InstallmentValidation(
            components_total_amount=document.validation.components_total_amount,
            sum_matches_total=document.validation.sum_matches_total,
            pay_until_matches_due_date=document.validation.pay_until_matches_due_date,
        ),
        semantic_markers=_semantic_markers(text),
    )


def _draft_from_federal(
    guide: FederalRevenueGuide,
    text: str,
    page: int,
    block: int,
) -> InstallmentDocumentDraft:
    components = tuple(
        InstallmentComponent(
            code=row.revenue_code,
            description=" - ".join(filter(None, (row.description, row.detail_description))),
            tax=_explicit_tax(" ".join(filter(None, (row.description, row.detail_description)))),
            reference_period=row.assessment_period,
            principal_amount=row.principal_amount,
            penalty_amount=row.penalty_amount,
            interest_amount=row.interest_amount,
            total_amount=row.total_amount,
        )
        for row in guide.revenues
    )
    return InstallmentDocumentDraft(
        header=InstallmentHeader(
            layout=FEDERAL_REVENUE_FORM_LAYOUT_ID,
            page_number=page,
            block_number=block,
            taxpayer_id=guide.header.taxpayer_id,
            taxpayer_id_kind=guide.header.taxpayer_id_kind,
            taxpayer_id_structure_valid=guide.header.taxpayer_id_structure_valid,
            taxpayer_name=guide.header.taxpayer_name,
        ),
        installment=_installment_identity(
            text,
            reference_period=guide.header.assessment_period,
            document_number=guide.header.document_number,
        ),
        payment=InstallmentPayment(
            due_date=guide.header.due_date,
            pay_until=guide.header.pay_until,
            principal_amount=_sum_amount(components, "principal_amount"),
            penalty_amount=_sum_amount(components, "penalty_amount"),
            interest_amount=_sum_amount(components, "interest_amount"),
            correction_amount=_sum_amount(components, "correction_amount"),
            total_amount=guide.header.total_amount,
        ),
        components=components,
        validation=InstallmentValidation(
            components_total_amount=guide.validation.revenues_total_amount,
            sum_matches_total=guide.validation.sum_matches_total,
            pay_until_matches_due_date=guide.validation.pay_until_matches_due_date,
        ),
        semantic_markers=_semantic_markers(text),
        layout_revenue_codes=tuple(row.revenue_code for row in guide.revenues),
        warning_codes=guide.warning_codes,
    )


def _draft_from_state(
    guide: ExtractedStateGuide,
    text: str,
    page: int,
    block: int,
) -> InstallmentDocumentDraft:
    components = tuple(
        InstallmentComponent(
            code=component.code or row.revenue_code,
            description=component.label,
            tax=_explicit_tax(" ".join(filter(None, (row.description, row.parent_description)))),
            reference_period=guide.header.reference_period,
            uf=guide.header.uf,
            principal_amount=component.amount if component.kind == "PRINCIPAL" else Decimal("0.00"),
            penalty_amount=component.amount if component.kind == "PENALTY" else Decimal("0.00"),
            interest_amount=component.amount if component.kind == "INTEREST" else Decimal("0.00"),
            correction_amount=component.amount if component.kind == "CORRECTION" else Decimal("0.00"),
            total_amount=component.amount,
        )
        for row in guide.revenues
        for component in row.components
    )
    identity = _installment_identity(
        text,
        reference_period=guide.header.reference_period,
        document_number=guide.header.document_number,
    )
    if guide.header.installment_reference and identity.installment_reference is None:
        identity = identity.model_copy(update={"installment_reference": guide.header.installment_reference})
    return InstallmentDocumentDraft(
        header=InstallmentHeader(
            layout=GO_DARE_51_LAYOUT_ID,
            page_number=page,
            block_number=block,
            taxpayer_id=guide.header.taxpayer_id,
            taxpayer_id_kind=guide.header.taxpayer_id_kind,
            taxpayer_id_structure_valid=guide.header.taxpayer_id_structure_valid,
            taxpayer_name=guide.header.taxpayer_name,
        ),
        installment=identity,
        payment=InstallmentPayment(
            due_date=guide.header.due_date,
            pay_until=guide.header.pay_until,
            principal_amount=_sum_amount(components, "principal_amount"),
            penalty_amount=_sum_amount(components, "penalty_amount"),
            interest_amount=_sum_amount(components, "interest_amount"),
            correction_amount=_sum_amount(components, "correction_amount"),
            total_amount=guide.header.total_amount,
        ),
        components=components,
        validation=InstallmentValidation(
            components_total_amount=guide.validation.components_total_amount,
            sum_matches_total=guide.validation.sum_matches_total,
            pay_until_matches_due_date=guide.validation.pay_until_matches_due_date,
        ),
        semantic_markers=_semantic_markers(text),
        layout_revenue_codes=tuple(row.revenue_code for row in guide.revenues),
        warning_codes=guide.warning_codes,
    )


def _draft_from_legacy(
    document: LegacyDarfDocument,
    text: str,
    page: int,
    block: int,
) -> InstallmentDocumentDraft:
    component = InstallmentComponent(
        code=document.revenue.revenue_code,
        description=None,
        reference_period=document.header.assessment_period,
        principal_amount=document.revenue.principal_amount,
        penalty_amount=document.revenue.penalty_amount,
        interest_amount=document.revenue.interest_amount,
        total_amount=document.revenue.total_amount,
    )
    return InstallmentDocumentDraft(
        header=InstallmentHeader(
            layout=LEGACY_DARF_FORM_LAYOUT_ID,
            page_number=page,
            block_number=block,
            taxpayer_id=document.header.taxpayer_id,
            taxpayer_id_kind=document.header.taxpayer_id_kind,
            taxpayer_id_structure_valid=document.header.taxpayer_id_structure_valid,
            taxpayer_name=document.header.taxpayer_name,
        ),
        installment=InstallmentIdentity(
            agreement_number=document.observation_reference,
            current_installment=document.observation_installment_number,
            reference_period=document.header.assessment_period,
            document_number=document.header.document_number,
        ),
        payment=InstallmentPayment(
            due_date=document.header.due_date,
            pay_until=document.header.pay_until,
            principal_amount=document.revenue.principal_amount,
            penalty_amount=document.revenue.penalty_amount,
            interest_amount=document.revenue.interest_amount,
            total_amount=document.revenue.total_amount,
        ),
        components=(component,),
        validation=InstallmentValidation(
            components_total_amount=document.validation.calculated_total_amount,
            sum_matches_total=document.validation.sum_matches_total,
        ),
        semantic_markers=_semantic_markers(text),
        layout_revenue_codes=(document.revenue.revenue_code,) if document.revenue.revenue_code else (),
        warning_codes=document.warning_codes,
    )


def _installment_identity(
    text: str,
    *,
    reference_period: GuidePeriod | None,
    document_number: str | None,
) -> InstallmentIdentity:
    normalized = search_text(text)
    agreement = _first_group(
        normalized,
        r"(?:NUMERO DO PARCELAMENTO|PARCELAMENTO(?:\s+N[RO.°º]*)?|PGFN-SISPAR)\s*:?-?\s*(\d{1,30})",
    )
    registration = _first_group(normalized, r"(?:INSCRICAO|REGISTRO)\s*:?-?\s*(\d{4,30})")
    pair = re.search(
        r"(?:NUMERO DA PARCELA|PARCELA)\s*:?-?\s*0*(\d{1,4})\s*(?:/|DE)\s*0*(\d{1,4})",
        normalized,
    )
    current = int(pair[1]) if pair else None
    total = int(pair[2]) if pair else None
    if pair is None:
        complementary = re.search(r"PARCELAMENTO\s+N[RO.°º]*\s*:?-?\s*\d{4,30}.*?0*(\d{1,4})\s*/\s*0*(\d{1,4})", normalized)
        if complementary:
            current, total = int(complementary[1]), int(complementary[2])
    standalone = _first_group(normalized, r"\bPARCELA\s*:?-?\s*0*(\d{1,4})(?!\s*(?:/|DE))")
    return InstallmentIdentity(
        installment_reference=standalone,
        agreement_number=agreement,
        registration_number=registration,
        current_installment=current or (int(standalone) if standalone else None),
        total_installments=total,
        reference_period=reference_period,
        document_number=document_number,
    )


def _classify_document(document: InstallmentDocumentDraft) -> InstallmentDocumentClassification:
    markers = set(document.semantic_markers)
    layout = document.header.layout
    codes = set(document.layout_revenue_codes)
    warnings: list[str] = list(document.warning_codes)
    program = InstallmentProgram.UNKNOWN
    administrator = InstallmentAdministrator.UNKNOWN
    scope = InstallmentDebtScope.UNKNOWN
    confidence = 0.70
    raw_debt_description = None

    if {"PGFN", "SISPAR"} <= markers or "PGFN-SISPAR" in markers:
        program, administrator, scope = (
            InstallmentProgram.PGFN,
            InstallmentAdministrator.PGFN,
            InstallmentDebtScope.FEDERAL,
        )
        raw_debt_description = "DIVIDA_ATIVA"
        confidence = 1.0
    elif markers & {"PARCMEI", "SIMEI"}:
        program, administrator, scope = (
            InstallmentProgram.PARCMEI,
            InstallmentAdministrator.SIMPLES_NACIONAL,
            InstallmentDebtScope.SIMEI,
        )
        confidence = 1.0
    elif markers & {"RELPSN", "RELP"}:
        program, administrator, scope = (
            InstallmentProgram.RELP,
            InstallmentAdministrator.SIMPLES_NACIONAL,
            InstallmentDebtScope.SIMPLES_NACIONAL,
        )
        confidence = 1.0
    elif markers & {"PERTSN", "PERT"}:
        program, administrator, scope = (
            InstallmentProgram.PERT,
            InstallmentAdministrator.SIMPLES_NACIONAL,
            InstallmentDebtScope.SIMPLES_NACIONAL,
        )
        confidence = 1.0
    elif "PARCSN" in markers:
        program, administrator, scope = (
            InstallmentProgram.PARCSN,
            InstallmentAdministrator.SIMPLES_NACIONAL,
            InstallmentDebtScope.SIMPLES_NACIONAL,
        )
        confidence = 1.0
    elif layout == LEGACY_DARF_FORM_LAYOUT_ID and _SIMPLIFIED_INSTALLMENT_REVENUE_CODE in codes:
        program, administrator, scope = (
            InstallmentProgram.SIMPLIFICADO,
            InstallmentAdministrator.RFB,
            InstallmentDebtScope.FEDERAL,
        )
        confidence = 1.0
    elif layout == GO_DARE_51_LAYOUT_ID and "PARCELAMENTO" in markers:
        program, administrator, scope = (
            InstallmentProgram.SEFAZ,
            InstallmentAdministrator.SEFAZ_GO,
            InstallmentDebtScope.STATE,
        )
        confidence = 1.0
    else:
        warnings.append("INSTALLMENT_PROGRAM_UNKNOWN")

    taxes = tuple(sorted({component.tax for component in document.components if component.tax}))
    if not taxes:
        warnings.append("INSTALLMENT_TAXES_UNKNOWN")
    return InstallmentDocumentClassification(
        program=program,
        administrator=administrator,
        debt_scope=scope,
        taxes=taxes,
        raw_debt_description=raw_debt_description,
        confidence=confidence,
        warning_codes=tuple(dict.fromkeys(warnings)),
    )


def _serialize_result(
    extracted: InstallmentLayoutExtraction,
    classified: ClassificationResult,
) -> dict[str, object]:
    result = InstallmentClassificationResult.model_validate(classified)
    documents = tuple(
        InstallmentDocument(
            header=draft.header,
            program=classification.program,
            administrator=classification.administrator,
            installment=draft.installment,
            debt=InstallmentDebt(
                scope=classification.debt_scope,
                taxes=classification.taxes,
                original_debt_periods=_original_debt_periods(draft),
                raw_debt_description=classification.raw_debt_description,
            ),
            payment=draft.payment,
            components=draft.components,
            validation=draft.validation,
            warning_codes=classification.warning_codes,
        )
        for draft, classification in zip(extracted.documents, result.documents, strict=True)
    )
    return InstallmentFile(documents=documents).model_dump(mode="json")


def _require_drafts(drafts: tuple[InstallmentDocumentDraft, ...]) -> InstallmentLayoutExtraction:
    if not drafts:
        raise LayoutExtractionFailure(ExtractionStatus.UNSUPPORTED, "UNKNOWN_INSTALLMENT_LAYOUT")
    return InstallmentLayoutExtraction(documents=drafts)


def _month_period(value: str | None) -> GuidePeriod | None:
    if not value or not re.fullmatch(r"\d{4}-(?:0[1-9]|1[0-2])", value):
        return None
    return GuidePeriod(
        label=value,
        kind=PeriodKind.MONTH,
        month=value,
        year=int(value[:4]),
    )


def _original_debt_periods(document: InstallmentDocumentDraft) -> tuple[GuidePeriod, ...]:
    if document.header.layout not in {DAS_FORM_LAYOUT_ID, FEDERAL_REVENUE_FORM_LAYOUT_ID}:
        return ()
    periods: list[GuidePeriod] = []
    observed: set[str] = set()
    for component in document.components:
        period = component.reference_period
        if period is None:
            continue
        identity = period.model_dump_json()
        if identity not in observed:
            observed.add(identity)
            periods.append(period)
    return tuple(periods)


def _sum_amount(components: tuple[InstallmentComponent, ...], field: str) -> Decimal | None:
    values = [getattr(component, field) for component in components]
    return sum((value for value in values if value is not None), Decimal("0.00")) if any(
        value is not None for value in values
    ) else None


def _explicit_tax(value: str) -> str | None:
    normalized = search_text(value)
    for marker, tax in (
        ("COFINS", "COFINS"),
        ("CSLL", "CSLL"),
        ("IRPJ", "IRPJ"),
        ("PIS", "PIS"),
        ("INSS", "INSS"),
        ("ICMS", "ICMS"),
        ("ISS", "ISS"),
    ):
        if re.search(rf"\b{marker}\b", normalized):
            return tax
    return None


def _first_group(value: str, pattern: str) -> str | None:
    match = re.search(pattern, value)
    return match[1] if match else None


def _empty(status: ExtractionStatus, warning: str) -> ParserExtraction:
    return ParserExtraction(
        document_family="UNKNOWN",
        extraction_status=status,
        warnings=(warning,),
    )
