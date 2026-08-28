from __future__ import annotations

from pydantic import BaseModel


class CockpitCompanyRow(BaseModel):
    company_id: int
    razao_social: str
    nome_fantasia: str | None
    cnpj: str
    inscricao_estadual_display: str
    regime_label: str
    department: str | None
    source: str | None
    overall_status: str
    obligations_total: int
    delivered_total: int
    pending_total: int
    divergences_total: int
    dctfweb_origin: str | None = None
    dctfweb_department: str | None = None
    factor_r_status: str | None = None
    factor_r_calculation_status: str | None = None
    factor_r_reconciliation_status: str | None = None
    factor_r_confidence: str | None = None
    factor_r_estimated: str | None = None
    factor_r_observed: str | None = None


class CockpitResponse(BaseModel):
    period: str
    items: list[CockpitCompanyRow]
