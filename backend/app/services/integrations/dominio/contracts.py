from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any


class DominioDocumentContract(str, Enum):
    DOMINIO_FOLHA_RESUMO = "DOMINIO_FOLHA_RESUMO"


class DominioEvidenceSource(str, Enum):
    DOMINIO_FOLHA_PDF = "DOMINIO_FOLHA_PDF"


class DominioSelectionScope(str, Enum):
    ATIVAS = "ATIVAS"


class DominioPayrollBlockType(str, Enum):
    MONTHLY_PAYROLL = "MONTHLY_PAYROLL"
    SALARY_ADJUSTMENT = "SALARY_ADJUSTMENT"
    PAYMENT_ENTRY = "PAYMENT_ENTRY"
    COMPLEMENTARY = "COMPLEMENTARY"
    UNKNOWN = "UNKNOWN"


class DominioPayrollSectionType(str, Enum):
    EARNINGS = "EARNINGS"
    DEDUCTIONS = "DEDUCTIONS"
    INFORMATIONAL = "INFORMATIONAL"


class DominioInformedValueKind(str, Enum):
    HOURS = "HOURS"
    DECIMAL = "DECIMAL"
    UNKNOWN = "UNKNOWN"


class DominioCnpjStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    MISSING = "MISSING"


class DominioParserConfidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class DominioPayrollWarningCode(str, Enum):
    PAGE_HEADER_MISSING = "PAGE_HEADER_MISSING"
    COMPANY_HEADER_INCOMPLETE = "COMPANY_HEADER_INCOMPLETE"
    INVALID_CNPJ = "INVALID_CNPJ"
    MISSING_CNPJ = "MISSING_CNPJ"
    INVALID_COMPETENCE = "INVALID_COMPETENCE"
    FILE_NAME_COMPETENCE_MISMATCH = "FILE_NAME_COMPETENCE_MISMATCH"
    DECLARED_PAGE_SEQUENCE_MISMATCH = "DECLARED_PAGE_SEQUENCE_MISMATCH"
    CONTINUATION_PAGE_EMPTY = "CONTINUATION_PAGE_EMPTY"
    UNKNOWN_BLOCK_HEADING = "UNKNOWN_BLOCK_HEADING"
    RUBRIC_LINE_UNPARSED = "RUBRIC_LINE_UNPARSED"
    INFORMED_VALUE_UNPARSED = "INFORMED_VALUE_UNPARSED"
    CALCULATED_VALUE_UNPARSED = "CALCULATED_VALUE_UNPARSED"
    SECTION_TOTAL_WITHOUT_SECTION = "SECTION_TOTAL_WITHOUT_SECTION"
    SECTION_TOTAL_MISMATCH = "SECTION_TOTAL_MISMATCH"
    NET_TOTAL_MISSING = "NET_TOTAL_MISSING"
    MULTIPLE_COMPETENCES_IN_FILE = "MULTIPLE_COMPETENCES_IN_FILE"
    TEXT_LAYER_MISSING = "TEXT_LAYER_MISSING"
    NO_COMPANY_BLOCKS_FOUND = "NO_COMPANY_BLOCKS_FOUND"


@dataclass(frozen=True, slots=True)
class DominioPayrollObservedFields:
    dominio_company_code: str
    company_cnpj: str
    company_name: str
    source_payroll_competence: str
    assessment_competence: str
    calculation_type: str
    source_pages: tuple[int, ...]
    raw_text: str
    has_payroll: bool
    has_employee: bool
    has_pro_labore: bool
    has_autonomous: bool
    has_inss: bool
    has_fgts: bool
    has_termination: bool
    has_vacation: bool
    has_leave: bool
    gross_total: str | None = None
    discount_total: str | None = None
    informative_total: str | None = None
    net_total: str | None = None


@dataclass(frozen=True, slots=True)
class DominioPayrollWarning:
    code: DominioPayrollWarningCode
    message: str
    physical_page_number: int | None = None
    company_key: str | None = None
    line: str | None = None
    context: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class DominioPayrollSignalEvidence:
    signal: str
    value: bool
    rubric_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DominioPayrollRubric:
    code: str
    original_name: str
    normalized_name: str
    contributors_count: int
    informed_value_raw: str
    informed_value_kind: DominioInformedValueKind
    informed_value_decimal: Decimal | None
    informed_value_minutes: int | None
    calculated_value: Decimal | None
    marked_with_asterisk: bool
    section: DominioPayrollSectionType
    block_type: DominioPayrollBlockType
    physical_page_number: int
    line_order: int
    warnings: tuple[DominioPayrollWarning, ...] = ()


@dataclass(frozen=True, slots=True)
class DominioPayrollSection:
    section_type: DominioPayrollSectionType
    physical_page_numbers: tuple[int, ...]
    line_orders: tuple[int, ...]
    declared_total: Decimal | None
    calculated_total: Decimal
    rubric_codes: tuple[str, ...]
    warnings: tuple[DominioPayrollWarning, ...] = ()


@dataclass(frozen=True, slots=True)
class DominioPayrollBlock:
    block_type: DominioPayrollBlockType
    description: str
    source_competence: str | None
    event_date: str | None
    payment_date: str | None
    sections: tuple[DominioPayrollSection, ...]
    rubrics: tuple[DominioPayrollRubric, ...]
    declared_totals: dict[str, Decimal]
    warnings: tuple[DominioPayrollWarning, ...] = ()


@dataclass(frozen=True, slots=True)
class DominioPayrollCompany:
    dominio_company_code: str
    company_cnpj: str | None
    company_cnpj_raw: str | None
    company_cnpj_status: DominioCnpjStatus
    company_name: str
    source_payroll_competence: str | None
    assessment_competence: str | None
    calculation_type: str | None
    physical_page_numbers: tuple[int, ...]
    declared_page_numbers: tuple[int, ...]
    declared_page_count: int | None
    blocks: tuple[DominioPayrollBlock, ...]
    rubrics: tuple[DominioPayrollRubric, ...]
    has_payroll: bool
    has_employee: bool
    has_pro_labore: bool
    has_autonomous: bool
    has_inss: bool
    has_fgts: bool
    has_termination: bool
    has_vacation: bool
    has_leave: bool
    gross_total: Decimal | None
    discount_total: Decimal | None
    informative_total: Decimal | None
    net_total: Decimal | None
    raw_text: str
    confidence: DominioParserConfidence
    warnings: tuple[DominioPayrollWarning, ...]
    signal_sources: tuple[DominioPayrollSignalEvidence, ...]

    @property
    def company_key(self) -> str:
        competence = self.source_payroll_competence or "missing-competence"
        cnpj = self.company_cnpj or self.company_cnpj_raw or "missing-cnpj"
        return f"{self.dominio_company_code}|{cnpj}|{competence}"


@dataclass(frozen=True, slots=True)
class DominioPayrollReport:
    source_file_name: str
    source: DominioDocumentContract
    evidence_source: DominioEvidenceSource
    parser_version: str
    physical_page_count: int
    detected_source_competences: tuple[str, ...]
    detected_assessment_competences: tuple[str, ...]
    companies: tuple[DominioPayrollCompany, ...]
    warnings: tuple[DominioPayrollWarning, ...]
