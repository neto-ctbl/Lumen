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


class CockpitResponse(BaseModel):
    period: str
    items: list[CockpitCompanyRow]
