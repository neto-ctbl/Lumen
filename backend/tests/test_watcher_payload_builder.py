from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agent.watcher.config import DEFAULT_WATCHER_ROOT, WatcherConfig
from agent.watcher.payload_builder import build_watcher_event_payload
from backend.tests.test_watcher_contract import WatcherEventContract, _validate_json_schema_instance
from backend.tests.watcher_agent_test_utils import watcher_pdf_path, write_synthetic_pdf


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_config_is_lazy_and_uses_only_reserved_root_setting() -> None:
    config = WatcherConfig.from_env({"LUMEN_WATCHER_ROOT": r"Z:\SYNTHETIC"})
    assert config.root == Path(r"Z:\SYNTHETIC")
    assert WatcherConfig().root == DEFAULT_WATCHER_ROOT


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
