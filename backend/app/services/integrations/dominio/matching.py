from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.dominio_payroll import DominioPayrollMatchStatus
from backend.app.models.external_company import ExternalCompany
from backend.app.models.organization import Organization
from backend.app.services.integrations.dominio.contracts import DominioCnpjStatus


@dataclass(frozen=True, slots=True)
class DominioPayrollCompanyMatch:
    external_company_id: int | None
    match_status: str


def match_dominio_company_by_cnpj(
    session: Session,
    *,
    organization: Organization,
    company_cnpj: str | None,
    company_cnpj_status: DominioCnpjStatus,
) -> DominioPayrollCompanyMatch:
    if company_cnpj_status == DominioCnpjStatus.MISSING or not company_cnpj:
        return DominioPayrollCompanyMatch(
            external_company_id=None,
            match_status=DominioPayrollMatchStatus.MISSING_CNPJ.value,
        )
    if company_cnpj_status == DominioCnpjStatus.INVALID:
        return DominioPayrollCompanyMatch(
            external_company_id=None,
            match_status=DominioPayrollMatchStatus.INVALID_CNPJ.value,
        )

    candidates = session.scalars(
        select(ExternalCompany).where(
            ExternalCompany.organization_id == organization.id,
            ExternalCompany.cnpj == company_cnpj,
        )
    ).all()
    active_candidates = [candidate for candidate in candidates if candidate.active]
    if len(active_candidates) == 1:
        return DominioPayrollCompanyMatch(
            external_company_id=active_candidates[0].id,
            match_status=DominioPayrollMatchStatus.MATCHED.value,
        )
    if len(active_candidates) > 1:
        return DominioPayrollCompanyMatch(
            external_company_id=None,
            match_status=DominioPayrollMatchStatus.AMBIGUOUS.value,
        )
    return DominioPayrollCompanyMatch(
        external_company_id=None,
        match_status=DominioPayrollMatchStatus.UNMATCHED.value,
    )
