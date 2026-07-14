from __future__ import annotations

from pydantic import BaseModel


class EvidenceItem(BaseModel):
    id: int
    company_id: int | None
    company_name: str | None
    source: str
    source_type: str
    file_name: str | None
    detected_tax: str | None
    detected_obligation: str | None
    competencia_detected: str | None
    status: str
    created_at: str | None


class EvidenceListResponse(BaseModel):
    period: str
    items: list[EvidenceItem]
