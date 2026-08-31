from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from agent.watcher.path_contract import (
    folder_period_to_competence,
    normalize_relative_path,
    watcher_event_fingerprint,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "backend" / "tests" / "fixtures" / "watcher"
SCHEMA_PATH = REPO_ROOT / "schemas" / "watcher_event.schema.json"


class PdfProbeContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_pdf: bool
    page_count: int = Field(ge=0)
    has_extractable_text: bool
    text_length: int = Field(ge=0)


class WatcherEventContract(BaseModel):
    """Runtime mirror for the versioned JSON Schema until ingest exists."""

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
    pdf_probe: PdfProbeContract

    @field_validator("relative_path")
    @classmethod
    def reject_absolute_path(cls, value: str) -> str:
        if value.startswith(("\\", "/")) or (len(value) >= 2 and value[1] == ":"):
            raise ValueError("relative_path must not be absolute or UNC")
        return value


def _fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def _validate_json_schema_instance(value: object, schema: dict[str, object]) -> None:
    """Validate the Draft 2020-12 subset used by this versioned contract."""
    if "const" in schema and value != schema["const"]:
        raise ValueError("const mismatch")
    expected_type = schema.get("type")
    if expected_type == "object":
        if not isinstance(value, dict):
            raise ValueError("expected object")
        properties = schema.get("properties", {})
        assert isinstance(properties, dict)
        required = schema.get("required", [])
        assert isinstance(required, list)
        if any(field not in value for field in required):
            raise ValueError("missing required field")
        if schema.get("additionalProperties") is False and any(field not in properties for field in value):
            raise ValueError("additional property")
        for field, child_schema in properties.items():
            if field in value:
                assert isinstance(child_schema, dict)
                _validate_json_schema_instance(value[field], child_schema)
        return
    if expected_type == "string":
        if not isinstance(value, str):
            raise ValueError("expected string")
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", len(value)):
            raise ValueError("string length")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.fullmatch(pattern, value) is None:
            raise ValueError("string pattern")
    elif expected_type == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("expected integer")
        if value < schema.get("minimum", value):
            raise ValueError("integer minimum")
    elif expected_type == "boolean" and not isinstance(value, bool):
        raise ValueError("expected boolean")


def test_valid_fixture_passes_versioned_schema_contract() -> None:
    payload = _fixture("watcher_event_valid.json")
    WatcherEventContract.model_validate(payload)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    _validate_json_schema_instance(payload, schema)
    assert schema["additionalProperties"] is False
    assert schema["properties"]["schema_version"]["const"] == "1"
    assert schema["properties"]["event_type"]["const"] == "FILE_STABLE"


@pytest.mark.parametrize(
    ("field", "value"),
    [("file_sha256", "invalid"), ("folder_period", "07-2026")],
)
def test_invalid_required_format_is_rejected(field: str, value: str) -> None:
    payload = _fixture("watcher_event_valid.json")
    payload[field] = value
    with pytest.raises(ValidationError):
        WatcherEventContract.model_validate(payload)
    with pytest.raises(ValueError):
        _validate_json_schema_instance(payload, json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))


def test_secret_and_absolute_path_are_rejected() -> None:
    with pytest.raises(ValidationError):
        WatcherEventContract.model_validate(_fixture("watcher_event_invalid_secret.json"))
    with pytest.raises(ValueError):
        _validate_json_schema_instance(
            _fixture("watcher_event_invalid_secret.json"), json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        )

    payload = _fixture("watcher_event_valid.json")
    payload["relative_path"] = r"G:\EMPRESAS\EMPRESA EXEMPLO\DAS 07-2026.pdf"
    with pytest.raises(ValidationError):
        WatcherEventContract.model_validate(payload)
    with pytest.raises(ValueError):
        _validate_json_schema_instance(payload, json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))


def test_traversal_is_rejected_by_path_grammar() -> None:
    payload = _fixture("watcher_event_invalid_traversal.json")
    WatcherEventContract.model_validate(payload)
    with pytest.raises(ValueError, match="escapes"):
        normalize_relative_path(str(payload["relative_path"]))


def test_fingerprint_is_deterministic_and_ignores_event_type() -> None:
    payload = _fixture("watcher_event_valid.json")
    baseline = watcher_event_fingerprint(7, str(payload["relative_path"]), str(payload["file_sha256"]))
    assert baseline == watcher_event_fingerprint(7, str(payload["relative_path"]), str(payload["file_sha256"]))
    payload["event_type"] = "CREATED"
    assert baseline == watcher_event_fingerprint(7, str(payload["relative_path"]), str(payload["file_sha256"]))
    assert baseline != watcher_event_fingerprint(7, str(payload["relative_path"]), "f" * 64)
    assert baseline != watcher_event_fingerprint(7, r"OUTRA EMPRESA\Escrita Fiscal\07-2026\DAS 07-2026.pdf", str(payload["file_sha256"]))


def test_case_insensitive_path_identity_and_fiscal_period_grammar() -> None:
    first = r"EMPRESA EXEMPLO\Escrita Fiscal\07-2026\Guias\DAS.pdf"
    second = r"empresa exemplo/escrita fiscal/07-2026/guias/das.PDF"
    assert normalize_relative_path(first) == normalize_relative_path(second)
    assert watcher_event_fingerprint(7, first, "a" * 64) == watcher_event_fingerprint(7, second, "a" * 64)
    assert folder_period_to_competence("07-2026") == "2026-07"


def test_fixtures_are_synthetic_and_do_not_embed_secrets() -> None:
    fixture_blob = "\n".join(path.read_text(encoding="utf-8") for path in FIXTURES_DIR.glob("*.json"))
    assert "12.345.678/" not in fixture_blob
    assert "Authorization" not in fixture_blob
    assert "Bearer " not in fixture_blob
    assert "password" not in fixture_blob.casefold()
    assert "EMPRESA EXEMPLO" in fixture_blob
