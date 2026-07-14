from __future__ import annotations

from pydantic import BaseModel


class IntegrationHealthItem(BaseModel):
    provider: str
    label: str
    status: str
    account_status: str | None
    last_run_status: str | None
    last_run_at: str | None
    processed_count: int
    error_count: int
    note: str


class IntegrationHealthResponse(BaseModel):
    items: list[IntegrationHealthItem]
