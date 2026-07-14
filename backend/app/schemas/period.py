from __future__ import annotations

from pydantic import BaseModel


class PeriodItem(BaseModel):
    id: int
    competencia: str
    year: int
    month: int
    status: str


class PeriodListResponse(BaseModel):
    items: list[PeriodItem]
