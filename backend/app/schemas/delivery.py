from __future__ import annotations

from pydantic import BaseModel


class DeliveryItem(BaseModel):
    obligation_status_id: int
    company_id: int
    company_name: str
    cnpj: str
    obligation_code: str
    obligation_name: str
    status: str
    department: str
    source: str | None
    due_date: str | None
    delivered_at: str | None


class DeliveryListResponse(BaseModel):
    period: str
    items: list[DeliveryItem]
