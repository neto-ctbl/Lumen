from __future__ import annotations

from pydantic import BaseModel


class DivergenceItem(BaseModel):
    id: int
    company_id: int | None
    company_name: str | None
    code: str
    title: str
    message: str
    severity: str
    department: str
    source: str
    status: str
    created_at: str | None


class DivergenceListResponse(BaseModel):
    period: str
    items: list[DivergenceItem]
