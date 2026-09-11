from __future__ import annotations

from datetime import datetime
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class WatcherDocumentEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: Literal["FILE_STABLE"]
    detected_at: datetime


class WatcherDocumentFileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relative_path: str = Field(min_length=1, max_length=500)
    file_name: str = Field(min_length=1, max_length=255)
    extension: Literal[".pdf", ".json", ".xml", ".zip"]
    size: int = Field(ge=0)
    mtime_ns: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")


class WatcherPathContextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enterprise_folder_candidate: str = Field(min_length=1, max_length=255)
    fiscal_root: Literal["Escrita Fiscal"]
    segments_below_fiscal_root: list[str] = Field(max_length=100)
    period_candidates: list[str] = Field(max_length=100)
    period_ambiguous: bool
    classifier_hint: str = Field(min_length=1, max_length=100)

    @field_validator("segments_below_fiscal_root")
    @classmethod
    def validate_segments(cls, values: list[str]) -> list[str]:
        if any(not value or len(value) > 255 or value in {".", ".."} for value in values):
            raise ValueError("path segments must be non-empty relative names")
        return values

    @field_validator("period_candidates")
    @classmethod
    def validate_period_candidates(cls, values: list[str]) -> list[str]:
        if any(re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value) is None for value in values):
            raise ValueError("period candidates must use YYYY-MM")
        if len(values) != len(set(values)):
            raise ValueError("period candidates must be distinct")
        return values


class WatcherTechnicalProbeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Literal["PDF", "JSON", "XML", "ZIP"]
    valid: bool


class WatcherDocumentCandidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal[2]
    event: WatcherDocumentEventRequest
    file: WatcherDocumentFileRequest
    path_context: WatcherPathContextRequest
    technical_probe: WatcherTechnicalProbeRequest


WatcherIngestRequest = WatcherEventIngestRequest | WatcherDocumentCandidateRequest


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
