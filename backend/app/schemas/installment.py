from __future__ import annotations

from pydantic import BaseModel


class InstallmentItem(BaseModel):
    id: int
    company_id: int
    company_name: str
    tipo: str
    protocolo: str | None
    quantidade_parcelas: int | None
    parcela_atual: int | None
    valor_parcela: float | None
    vencimento: str | None
    status: str
    source: str
    ultima_competencia_detectada: str | None


class InstallmentListResponse(BaseModel):
    period: str
    items: list[InstallmentItem]
