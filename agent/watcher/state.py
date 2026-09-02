"""Atomic, local-only state for the polling watcher."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any


STATE_VERSION = 1


@dataclass(slots=True)
class FileDeliveryState:
    last_seen_size: int
    last_seen_mtime_ns: int
    stable_since: float
    last_seen_sha256: str | None = None
    last_sent_sha256: str | None = None
    delivery_status: str = "OBSERVING"
    retry_count: int = 0
    next_retry_at: float | None = None


@dataclass(slots=True)
class WatcherState:
    initialized: bool = False
    files: dict[str, FileDeliveryState] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StateLoadResult:
    state: WatcherState
    recovered_corrupt_state: bool = False


class WatcherStateStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> StateLoadResult:
        if not self.path.exists():
            return StateLoadResult(WatcherState())
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if raw.get("version") != STATE_VERSION or not isinstance(raw.get("files"), dict):
                raise ValueError("unsupported watcher state")
            files = {
                relative_path: FileDeliveryState(**value)
                for relative_path, value in raw["files"].items()
                if isinstance(relative_path, str) and isinstance(value, dict)
            }
            return StateLoadResult(WatcherState(initialized=bool(raw.get("initialized")), files=files))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            self._quarantine_corrupt_state()
            return StateLoadResult(WatcherState(), recovered_corrupt_state=True)

    def save(self, state: WatcherState) -> None:
        payload = {
            "version": STATE_VERSION,
            "initialized": state.initialized,
            "files": {key: asdict(value) for key, value in state.files.items()},
        }
        self._write_json_atomically(self.path, payload)

    def write_health(self, path: str | Path, payload: dict[str, Any]) -> None:
        self._write_json_atomically(Path(path), payload)

    def _quarantine_corrupt_state(self) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = self.path.with_name(f"{self.path.name}.corrupt-{timestamp}")
        try:
            self.path.replace(target)
        except OSError:
            # A failed quarantine must still fail closed into a no-send baseline.
            pass

    @staticmethod
    def _write_json_atomically(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f"{path.name}.tmp")
        serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
