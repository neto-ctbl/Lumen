from __future__ import annotations

from pydantic import BaseModel


class CompanySummary(BaseModel):
    id: int
    cnpj: str
    razao_social: str
    nome_fantasia: str | None
    apelido_pasta: str | None
    inscricao_estadual: str | None
    municipio: str | None
    uf: str | None
    active: bool
    regime_label: str


class CompanyListResponse(BaseModel):
    items: list[CompanySummary]


class CompanySummaryKpis(BaseModel):
    obligations_total: int
    delivered_total: int
    pending_total: int
    divergences_total: int
    evidences_total: int
    installments_total: int


class CompanyObligationPreview(BaseModel):
    obligation_code: str
    obligation_name: str
    status: str
    department: str
    source: str | None
    due_date: str | None
    delivered_at: str | None


class CompanyDetailResponse(BaseModel):
    company: CompanySummary
    period: str
    cnpj: str
    inscricao_estadual_display: str
    municipio_uf: str
    regime_label: str
    kpis: CompanySummaryKpis
    obligations: list[CompanyObligationPreview]
    evidences_preview: int
    divergences_preview: int
