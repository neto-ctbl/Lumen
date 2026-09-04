from __future__ import annotations

import json
from pathlib import Path

import agent.watcher.main as watcher_main
from agent.watcher.client import ClientResponse, WatcherApiClient
from agent.watcher.config import WatcherConfig
from agent.watcher.main import main
from agent.watcher.runtime import RuntimeSummary, WatcherRuntime
from agent.watcher.state import WatcherStateStore
from backend.tests.watcher_agent_test_utils import watcher_pdf_path, write_synthetic_pdf


class Clock:
    def __init__(self) -> None:
        self.value = 1000.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def _config(root: Path, state_path: Path, health_path: Path) -> WatcherConfig:
    return WatcherConfig(root=root, agent_token="synthetic-agent-token", stable_seconds=5, state_path=state_path, health_path=health_path)


def test_first_boot_baselines_existing_pdfs_without_sending(tmp_path: Path) -> None:
    existing = watcher_pdf_path(tmp_path, name="documento.pdf")
    write_synthetic_pdf(existing)
    calls: list[dict[str, object]] = []
    runtime = WatcherRuntime(
        _config(tmp_path, tmp_path / "state.json", tmp_path / "health.json"),
        client=WatcherApiClient(_config(tmp_path, tmp_path / "state.json", tmp_path / "health.json"), transport=lambda *_: calls.append({}) or ClientResponse(200, "SUCCESS")),
    )

    summary = runtime.run_once()

    assert summary.status == "RUNNING"
    assert summary.candidates_seen == 1
    assert not calls
    assert WatcherStateStore(tmp_path / "state.json").load().state.files


def test_runtime_uses_running_while_alive_and_stopped_after_clean_shutdown(tmp_path: Path) -> None:
    config = _config(tmp_path, tmp_path / "state.json", tmp_path / "health.json")
    heartbeats: list[str] = []
    runtime = WatcherRuntime(
        config,
        client=WatcherApiClient(config, transport=lambda _url, body, *_: heartbeats.append(json.loads(body)["status"]) or ClientResponse(204, "SUCCESS")),
    )

    runtime.mark_starting()
    assert json.loads(config.health_path.read_text(encoding="utf-8"))["status"] == "STARTING"
    assert runtime.run_once().status == "RUNNING"
    assert json.loads(config.health_path.read_text(encoding="utf-8"))["status"] == "RUNNING"
    runtime.stop_and_send_heartbeat()

    health = json.loads(config.health_path.read_text(encoding="utf-8"))
    assert health["status"] == "STOPPED"
    assert health["last_error_code"] is None
    assert health["last_scan_at"]
    assert heartbeats == ["STOPPED"]


def test_once_stops_and_preserves_a_degraded_diagnostic(tmp_path: Path, monkeypatch) -> None:
    state_path, health_path = tmp_path / "state.json", tmp_path / "health.json"
    monkeypatch.setenv("LUMEN_WATCHER_ROOT", str(tmp_path))
    monkeypatch.setenv("LUMEN_WATCHER_STATE_PATH", str(state_path))
    monkeypatch.setenv("LUMEN_WATCHER_HEALTH_PATH", str(health_path))
    monkeypatch.setenv("LUMEN_WATCHER_STABLE_SECONDS", "0")
    monkeypatch.delenv("LUMEN_WATCHER_AGENT_TOKEN", raising=False)

    assert main(["--once"]) == 0  # Empty root baseline.
    write_synthetic_pdf(watcher_pdf_path(tmp_path, name="documento.pdf"))
    assert main(["--once"]) == 0  # First observation.
    assert main(["--once"]) == 0  # Stable candidate reaches the client.

    health = json.loads(health_path.read_text(encoding="utf-8"))
    assert health["status"] == "STOPPED"
    assert health["last_error_code"] == "AUTH_CONFIGURATION"
    assert health["pending_retry"] == 1


def test_restart_discovers_new_unknown_filename_and_sends_after_stability(tmp_path: Path) -> None:
    clock = Clock()
    state_path, health_path = tmp_path / "state.json", tmp_path / "health.json"
    config = _config(tmp_path, state_path, health_path)
    sent: list[dict[str, object]] = []
    client = WatcherApiClient(config, transport=lambda _u, body, *_: sent.append(json.loads(body)) or ClientResponse(200, "SUCCESS"))
    WatcherRuntime(config, client=client, clock=clock).run_once()

    new_file = watcher_pdf_path(tmp_path, name="documento.pdf")
    write_synthetic_pdf(new_file)
    restarted = WatcherRuntime(config, client=client, clock=clock)
    assert restarted.run_once().pending_stability == 1
    clock.advance(5)
    assert restarted.run_once().sent_success == 1
    assert sent[0]["classifier_hint"] == "UNKNOWN"

    clock.advance(30)
    assert restarted.run_once().sent_success == 0


def test_changed_file_retries_transient_errors_then_succeeds_and_resets_backoff(tmp_path: Path) -> None:
    clock = Clock()
    state_path, health_path = tmp_path / "state.json", tmp_path / "health.json"
    config = _config(tmp_path, state_path, health_path)
    responses = iter([ClientResponse(503, "UNAVAILABLE"), ClientResponse(200, "SUCCESS")])
    runtime = WatcherRuntime(config, client=WatcherApiClient(config, transport=lambda *_: next(responses)), clock=clock)
    runtime.run_once()
    file_path = watcher_pdf_path(tmp_path)
    write_synthetic_pdf(file_path, text="FIRST")
    runtime.run_once()
    clock.advance(5)
    assert runtime.run_once().status == "DEGRADED"

    clock.advance(5)
    assert runtime.run_once().sent_success == 1
    state = WatcherStateStore(state_path).load().state
    item = next(iter(state.files.values()))
    assert item.retry_count == 0 and item.last_sent_sha256 == item.last_seen_sha256


def test_rejected_hash_is_not_retried_until_the_file_changes(tmp_path: Path) -> None:
    clock = Clock()
    config = _config(tmp_path, tmp_path / "state.json", tmp_path / "health.json")
    calls = 0

    def transport(*_args: object) -> ClientResponse:
        nonlocal calls
        calls += 1
        return ClientResponse(422, "REJECTED")

    runtime = WatcherRuntime(config, client=WatcherApiClient(config, transport=transport), clock=clock)
    runtime.run_once()
    file_path = watcher_pdf_path(tmp_path)
    write_synthetic_pdf(file_path)
    runtime.run_once()
    clock.advance(5)
    assert runtime.run_once().rejected == 1
    clock.advance(60)
    runtime.run_once()
    assert calls == 1


def test_status_command_reads_only_sanitized_health(tmp_path: Path, monkeypatch, capsys) -> None:
    health_path = tmp_path / "health.json"
    health_path.write_text(json.dumps({"status": "RUNNING", "token": "secret", "relative_path": "private.pdf"}), encoding="utf-8")
    monkeypatch.setenv("LUMEN_WATCHER_HEALTH_PATH", str(health_path))
    before = health_path.read_text(encoding="utf-8")
    assert main(["--status"]) == 0
    output = capsys.readouterr().out
    assert "RUNNING" in output
    assert "secret" not in output and "private.pdf" not in output
    assert health_path.read_text(encoding="utf-8") == before


def test_explicit_ingest_dry_run_does_not_send_and_confirmed_success_updates_state(tmp_path: Path) -> None:
    config = _config(tmp_path, tmp_path / "state.json", tmp_path / "health.json")
    path = watcher_pdf_path(tmp_path, name="manual.pdf")
    write_synthetic_pdf(path)
    calls: list[dict[str, object]] = []
    runtime = WatcherRuntime(
        config,
        client=WatcherApiClient(config, transport=lambda _url, body, *_: calls.append(json.loads(body)) or ClientResponse(200, "SUCCESS")),
    )

    payload, response = runtime.ingest_file(path, confirm_send=False)
    assert response is None and payload["file_name"] == "manual.pdf" and not calls
    _, response = runtime.ingest_file(path, confirm_send=True)
    assert response is not None and response.category == "SUCCESS" and len(calls) == 1
    item = next(iter(WatcherStateStore(config.state_path).load().state.files.values()))
    assert item.delivery_status == "SENT" and item.last_seen_sha256 == item.last_sent_sha256


def test_manual_ingest_command_records_clean_shutdown(tmp_path: Path, monkeypatch) -> None:
    state_path, health_path = tmp_path / "state.json", tmp_path / "health.json"
    path = watcher_pdf_path(tmp_path, name="manual-command.pdf")
    write_synthetic_pdf(path)
    monkeypatch.setenv("LUMEN_WATCHER_ROOT", str(tmp_path))
    monkeypatch.setenv("LUMEN_WATCHER_STATE_PATH", str(state_path))
    monkeypatch.setenv("LUMEN_WATCHER_HEALTH_PATH", str(health_path))

    assert main(["--ingest-file", str(path)]) == 0
    assert json.loads(health_path.read_text(encoding="utf-8"))["status"] == "STOPPED"


class _LifecycleRuntime:
    instances: list["_LifecycleRuntime"] = []
    next_status = "RUNNING"
    interrupt = False

    def __init__(self, _config: WatcherConfig) -> None:
        self.statuses: list[str] = []
        self.__class__.instances.append(self)

    def mark_starting(self) -> None:
        self.statuses.append("STARTING")

    def run_once(self) -> RuntimeSummary:
        if self.__class__.interrupt:
            raise KeyboardInterrupt
        return RuntimeSummary(self.__class__.next_status, 0, 0, 0, 0, 0, "ROOT_UNAVAILABLE" if self.__class__.next_status == "DEGRADED" else None)

    def send_heartbeat(self) -> ClientResponse:
        self.statuses.append(self.__class__.next_status)
        return ClientResponse(204, "SUCCESS")

    def stop_and_send_heartbeat(self) -> ClientResponse:
        self.statuses.append("STOPPED")
        return ClientResponse(204, "SUCCESS")

    def mark_fatal(self) -> None:
        self.statuses.append("FATAL")

    def ingest_file(self, _path: str, *, confirm_send: bool) -> tuple[dict[str, object], ClientResponse | None]:
        return {"file_sha256": "a" * 64}, ClientResponse(200, "SUCCESS") if confirm_send else None


def _fake_lifecycle(monkeypatch, *, status: str = "RUNNING", interrupt: bool = False) -> None:
    _LifecycleRuntime.instances = []
    _LifecycleRuntime.next_status = status
    _LifecycleRuntime.interrupt = interrupt
    monkeypatch.setattr(watcher_main, "WatcherRuntime", _LifecycleRuntime)


def test_once_sends_running_then_final_stopped_heartbeat(monkeypatch) -> None:
    _fake_lifecycle(monkeypatch)
    assert watcher_main.main(["--once"]) == 0
    assert _LifecycleRuntime.instances[-1].statuses == ["STARTING", "RUNNING", "STOPPED"]


def test_degraded_once_and_clean_interrupt_finish_with_stopped_heartbeat(monkeypatch) -> None:
    _fake_lifecycle(monkeypatch, status="DEGRADED")
    assert watcher_main.main(["--once"]) == 0
    assert _LifecycleRuntime.instances[-1].statuses[-1] == "STOPPED"

    _fake_lifecycle(monkeypatch, interrupt=True)
    assert watcher_main.main([]) == 0
    assert _LifecycleRuntime.instances[-1].statuses[-1] == "STOPPED"


def test_manual_dry_run_finishes_with_stopped_heartbeat(monkeypatch) -> None:
    _fake_lifecycle(monkeypatch)
    assert watcher_main.main(["--ingest-file", "synthetic.pdf"]) == 0
    assert _LifecycleRuntime.instances[-1].statuses[-1] == "STOPPED"


def test_failed_final_heartbeat_does_not_block_stopped_local_health(tmp_path: Path) -> None:
    config = _config(tmp_path, tmp_path / "state.json", tmp_path / "health.json")

    def unavailable(*_args: object) -> ClientResponse:
        raise OSError("synthetic network failure")

    runtime = WatcherRuntime(config, client=WatcherApiClient(config, transport=unavailable))
    runtime.mark_starting()
    assert runtime.stop_and_send_heartbeat() is None
    assert json.loads(config.health_path.read_text(encoding="utf-8"))["status"] == "STOPPED"
