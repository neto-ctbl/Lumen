from __future__ import annotations

from datetime import datetime
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator


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


class WatcherParserSignalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    value: JsonValue
    provenance: Literal["CONTENT", "FILE_STRUCTURE", "FILENAME", "PATH"]
    confidence: float | None = Field(default=None, ge=0, le=1)


class WatcherParserRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parser_name: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    parser_version: str = Field(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
    document_family: str = Field(min_length=1, max_length=100, pattern=r"^[A-Z][A-Z0-9_]*$")
    extraction_status: Literal["MATCHED", "UNSUPPORTED", "INCONCLUSIVE", "INVALID", "ERROR"]
    confidence: float | None = Field(default=None, ge=0, le=1)
    signals: list[WatcherParserSignalRequest] = Field(default_factory=list, max_length=200)
    warnings: list[str] = Field(default_factory=list, max_length=50)
    structured_data: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("warnings")
    @classmethod
    def validate_warnings(cls, values: list[str]) -> list[str]:
        if any(not value or len(value) > 500 for value in values):
            raise ValueError("warnings must contain short non-empty codes or messages")
        return values

    @model_validator(mode="after")
    def validate_safe_bounded_payload(self) -> WatcherParserRunRequest:
        forbidden = {
            "base64",
            "binary",
            "cookie",
            "digital_signature",
            "document_content",
            "file_bytes",
            "file_content",
            "raw_document",
            "raw_payload",
            "raw_text",
            "secret",
            "token",
        }
        keys = _nested_json_keys(self.structured_data)
        signal_names = {signal.name.casefold() for signal in self.signals}
        if (keys | signal_names) & forbidden:
            raise ValueError("parser run contains a forbidden raw-content or secret field")
        encoded = json.dumps(self.model_dump(mode="json"), ensure_ascii=True, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > 65_536:
            raise ValueError("parser run payload exceeds the metadata-only limit")
        return self


class WatcherParserRunResponse(BaseModel):
    parser_run_id: int
    parser_run_created: bool
    evidence_id: int
    parser_name: str
    parser_version: str
    extraction_status: str


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


def _nested_json_keys(value: JsonValue) -> set[str]:
    if isinstance(value, dict):
        return {str(key).casefold() for key in value} | {
            nested_key for nested in value.values() for nested_key in _nested_json_keys(nested)
        }
    if isinstance(value, list):
        return {nested_key for nested in value for nested_key in _nested_json_keys(nested)}
    return set()
