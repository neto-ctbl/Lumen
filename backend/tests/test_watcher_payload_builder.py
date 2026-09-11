from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agent.watcher.config import DEFAULT_WATCHER_ROOT, WatcherConfig
from agent.watcher.payload_builder import build_document_candidate_payload, build_watcher_event_payload
from backend.app.schemas.watcher import WatcherDocumentCandidateRequest
from backend.tests.test_watcher_contract import WatcherEventContract, _validate_json_schema_instance
from backend.tests.watcher_agent_test_utils import watcher_pdf_path, write_synthetic_pdf


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_config_is_lazy_and_uses_only_reserved_root_setting() -> None:
    config = WatcherConfig.from_env({"LUMEN_WATCHER_ROOT": r"Z:\SYNTHETIC"})
    assert config.root == Path(r"Z:\SYNTHETIC")
    assert WatcherConfig().root == DEFAULT_WATCHER_ROOT


def test_future_zip_limits_are_configurable_and_strictly_bounded() -> None:
    config = WatcherConfig.from_env(
        {
            "LUMEN_WATCHER_ZIP_MAX_ENTRIES": "25",
            "LUMEN_WATCHER_ZIP_MAX_UNCOMPRESSED_BYTES": "1048576",
            "LUMEN_WATCHER_ZIP_MAX_COMPRESSION_RATIO": "20",
            "LUMEN_WATCHER_ZIP_MAX_NESTING": "0",
        }
    )
    assert config.zip_max_entries == 25
    assert config.zip_max_uncompressed_bytes == 1048576
    assert config.zip_max_compression_ratio == 20
    assert config.zip_max_nesting == 0

    with pytest.raises(ValueError):
        WatcherConfig.from_env({"LUMEN_WATCHER_ZIP_MAX_ENTRIES": "0"})


def test_payload_is_deterministic_schema_valid_and_metadata_only(tmp_path: Path) -> None:
    file_path = watcher_pdf_path(tmp_path)
    write_synthetic_pdf(file_path, text="SYNTHETIC TEXT")
    detected_at = datetime(2026, 8, 31, 9, 0, tzinfo=timezone.utc)
    payload = build_watcher_event_payload(tmp_path, file_path, detected_at=detected_at)

    WatcherEventContract.model_validate(payload)
    schema = json.loads((REPO_ROOT / "schemas" / "watcher_event.schema.json").read_text(encoding="utf-8"))
    _validate_json_schema_instance(payload, schema)
    assert payload == build_watcher_event_payload(tmp_path, file_path, detected_at=detected_at)
    assert payload["relative_path"] == r"EMPRESA EXEMPLO\Escrita Fiscal\07-2026\Guias - Impostos e Parcelamentos\DAS 07-2026.pdf"
    assert payload["folder_period"] == "2026-07"
    assert payload["classifier_hint"] == "DAS"
    assert set(payload) == {
        "schema_version", "event_type", "relative_path", "file_name", "file_sha256", "file_size", "detected_at",
        "folder_period", "folder_company", "classifier_hint", "pdf_probe",
    }


def test_v2_payload_uses_flexible_candidates_without_final_company_or_period(tmp_path: Path) -> None:
    file_path = tmp_path / "EMPRESA EXEMPLO" / "Escrita Fiscal" / "Matriz" / "08-2026" / "DCTFWEB.pdf"
    file_path.parent.mkdir(parents=True)
    write_synthetic_pdf(file_path)
    detected_at = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)

    payload = build_document_candidate_payload(tmp_path, file_path, detected_at=detected_at)
    parsed = WatcherDocumentCandidateRequest.model_validate(payload)

    assert parsed.contract_version == 2
    assert parsed.file.extension == ".pdf" and parsed.file.mtime_ns > 0
    assert parsed.path_context.enterprise_folder_candidate == "EMPRESA EXEMPLO"
    assert parsed.path_context.segments_below_fiscal_root == ["Matriz", "08-2026"]
    assert parsed.path_context.period_candidates == ["2026-08"]
    assert parsed.path_context.period_ambiguous is False
    assert parsed.path_context.classifier_hint == "DCTFWEB"
    assert parsed.technical_probe.format == "PDF" and parsed.technical_probe.valid
    assert "company_id" not in str(payload) and "period_id" not in str(payload)
