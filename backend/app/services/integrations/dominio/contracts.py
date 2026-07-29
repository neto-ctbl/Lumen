from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DominioDocumentContract(str, Enum):
    DOMINIO_FOLHA_RESUMO = "DOMINIO_FOLHA_RESUMO"


class DominioEvidenceSource(str, Enum):
    DOMINIO_FOLHA_PDF = "DOMINIO_FOLHA_PDF"


class DominioSelectionScope(str, Enum):
    ATIVAS = "ATIVAS"


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
