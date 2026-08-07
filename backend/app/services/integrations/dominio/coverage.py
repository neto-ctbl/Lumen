from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.dominio_payroll import DominioPayrollCompanyMovement, DominioPayrollImport


@dataclass(frozen=True, slots=True)
class DominioPayrollCoverageRow:
    company_id: int
    source_payroll_competence: str | None
    assessment_competence: str | None
    imported: bool
    selection_scope: str


def list_dominio_payroll_coverage(
    session: Session,
    *,
    organization_id: int,
    company_id: int | None = None,
    source_payroll_competence: str | None = None,
    assessment_competence: str | None = None,
) -> list[DominioPayrollCoverageRow]:
    query = (
        select(DominioPayrollCompanyMovement, DominioPayrollImport)
        .join(DominioPayrollImport, DominioPayrollImport.id == DominioPayrollCompanyMovement.import_id)
        .where(DominioPayrollCompanyMovement.organization_id == organization_id)
        .order_by(DominioPayrollCompanyMovement.id.asc())
    )
    if company_id is not None:
        query = query.where(DominioPayrollCompanyMovement.external_company_id == company_id)
    if source_payroll_competence is not None:
        query = query.where(
            DominioPayrollCompanyMovement.source_payroll_competence == _parse_competence(source_payroll_competence)
        )
    if assessment_competence is not None:
        query = query.where(
            DominioPayrollCompanyMovement.assessment_competence == _parse_competence(assessment_competence)
        )
    rows = session.execute(query).all()
    return [
        DominioPayrollCoverageRow(
            company_id=movement.external_company_id or 0,
            source_payroll_competence=_format_competence(movement.source_payroll_competence),
            assessment_competence=_format_competence(movement.assessment_competence),
            imported=True,
            selection_scope=payroll_import.selection_scope,
        )
        for movement, payroll_import in rows
        if movement.external_company_id is not None
    ]


def _parse_competence(value: str) -> date:
    year_text, month_text = value.split("-", maxsplit=1)
    return date(int(year_text), int(month_text), 1)


def _format_competence(value: date | None) -> str | None:
    if value is None:
        return None
    return f"{value.year:04d}-{value.month:02d}"
