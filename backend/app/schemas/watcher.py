from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WatcherPdfProbeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_pdf: bool
    page_count: int = Field(ge=0)
    has_extractable_text: bool
    text_length: int = Field(ge=0)


class WatcherEventIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^1$")
    event_type: str = Field(pattern=r"^FILE_STABLE$")
    relative_path: str = Field(min_length=1, max_length=500)
    file_name: str = Field(min_length=1, max_length=255)
    file_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    file_size: int = Field(ge=0)
    detected_at: datetime
    folder_period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    folder_company: str = Field(min_length=1, max_length=255)
    classifier_hint: str = Field(min_length=1, max_length=100)
    pdf_probe: WatcherPdfProbeRequest


class WatcherEventIngestResponse(BaseModel):
    event_id: int
    evidence_id: int | None
    event_created: bool
    evidence_created: bool
    company_resolution: str
    period_resolution: str
    status: str
