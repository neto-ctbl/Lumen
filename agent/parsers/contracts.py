"""Common, metadata-safe contract for versioned document parsers."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class TechnicalFormat(str, Enum):
    PDF = "PDF"
    JSON = "JSON"
    XML = "XML"
    ZIP = "ZIP"


class ExtractionStatus(str, Enum):
    """Technical extraction outcome; never a fiscal reconciliation status."""

    MATCHED = "MATCHED"
    UNSUPPORTED = "UNSUPPORTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    INVALID = "INVALID"
    ERROR = "ERROR"


class SignalProvenance(str, Enum):
    CONTENT = "CONTENT"
    FILE_STRUCTURE = "FILE_STRUCTURE"
    FILENAME = "FILENAME"
    PATH = "PATH"


class DocumentSignal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    value: JsonValue
    provenance: SignalProvenance
    confidence: float | None = Field(default=None, ge=0, le=1)


class DocumentContext(BaseModel):
    """Local-only parser input. ``file_path`` must never be sent to the backend."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    file_path: Path
    technical_format: TechnicalFormat
    context_signals: tuple[DocumentSignal, ...] = Field(default_factory=tuple, max_length=100)


class ParserExtraction(BaseModel):
    """Parser-owned fields before the runtime attaches parser identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    document_family: str = Field(
        default="UNKNOWN",
        min_length=1,
        max_length=100,
        pattern=r"^[A-Z][A-Z0-9_]*$",
    )
    extraction_status: ExtractionStatus
    confidence: float | None = Field(default=None, ge=0, le=1)
    signals: tuple[DocumentSignal, ...] = Field(default_factory=tuple, max_length=100)
    warnings: tuple[str, ...] = Field(default_factory=tuple, max_length=50)
    structured_data: dict[str, JsonValue] = Field(default_factory=dict)


class ParserRunResult(BaseModel):
    """Standard output suitable for the metadata-only M2M endpoint."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    parser_name: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    parser_version: str = Field(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
    document_family: str = Field(min_length=1, max_length=100, pattern=r"^[A-Z][A-Z0-9_]*$")
    extraction_status: ExtractionStatus
    confidence: float | None = Field(default=None, ge=0, le=1)
    signals: tuple[DocumentSignal, ...] = Field(default_factory=tuple, max_length=200)
    warnings: tuple[str, ...] = Field(default_factory=tuple, max_length=50)
    structured_data: dict[str, JsonValue] = Field(default_factory=dict)

    def to_backend_payload(self) -> dict[str, object]:
        """Serialize only the explicit structured result, never the local path or file."""
        return self.model_dump(mode="json")


@runtime_checkable
class DocumentParser(Protocol):
    name: str
    version: str
    supported_formats: frozenset[TechnicalFormat]

    def supports(self, document: DocumentContext) -> bool:
        """Inspect without writes or external side effects."""
        ...

    def parse(self, document: DocumentContext) -> ParserExtraction:
        ...
