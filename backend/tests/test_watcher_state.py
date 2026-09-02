from __future__ import annotations

import json
from pathlib import Path

from agent.watcher.state import FileDeliveryState, WatcherState, WatcherStateStore


def test_state_is_atomic_and_never_persists_a_token(tmp_path: Path) -> None:
    path = tmp_path / "state" / "watcher_state.json"
    store = WatcherStateStore(path)
    state = WatcherState(initialized=True, files={"empresa\\documento.pdf": FileDeliveryState(10, 20, 30.0)})

    store.save(state)

    assert not path.with_name(f"{path.name}.tmp").exists()
    content = path.read_text(encoding="utf-8")
    assert "token" not in content.casefold()
    assert store.load().state.files["empresa\\documento.pdf"].last_seen_size == 10


def test_corrupt_state_is_quarantined_and_forces_a_new_baseline(tmp_path: Path) -> None:
    path = tmp_path / "watcher_state.json"
    path.write_text("not-json", encoding="utf-8")

    result = WatcherStateStore(path).load()

    assert result.recovered_corrupt_state
    assert not result.state.initialized
    assert list(tmp_path.glob("watcher_state.json.corrupt-*"))


def test_health_is_atomic_and_sanitized_by_callers(tmp_path: Path) -> None:
    path = tmp_path / "watcher_health.json"
    WatcherStateStore(tmp_path / "state.json").write_health(path, {"status": "RUNNING", "sent_success": 1})
    assert json.loads(path.read_text(encoding="utf-8")) == {"sent_success": 1, "status": "RUNNING"}
