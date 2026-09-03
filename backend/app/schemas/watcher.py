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


class WatcherHeartbeatCounters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidates_seen: int = Field(ge=0)
    pending_stability: int = Field(ge=0)
    pending_retry: int = Field(ge=0)
    sent_success: int = Field(ge=0)
    rejected: int = Field(ge=0)


class WatcherHeartbeatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = Field(pattern=r"^(STARTING|RUNNING|DEGRADED|STOPPED)$")
    started_at: datetime | None = None
    last_scan_at: datetime | None = None
    last_successful_send_at: datetime | None = None
    last_error_code: str | None = Field(default=None, max_length=100)
    counters: WatcherHeartbeatCounters


class WatcherHealthResponse(BaseModel):
    status: str
    reported_status: str | None
    received_at: datetime | None
    last_error_code: str | None
    started_at: datetime | None = None
    last_scan_at: datetime | None = None
    last_successful_send_at: datetime | None = None
    counters: dict[str, int]


class WatcherReprocessResponse(BaseModel):
    inspected: int
    evidence_created: int
    unresolved: int
