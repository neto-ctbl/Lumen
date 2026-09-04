"""Polling runtime that composes the S10.1 core and S10.2 ingest client."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Callable

from agent.watcher.client import ClientResponse, WatcherApiClient
from agent.watcher.config import WatcherConfig
from agent.watcher.payload_builder import PayloadBuildError, build_watcher_event_payload
from agent.watcher.scanner import DiscoveredFile, scan_fiscal_pdfs
from agent.watcher.state import FileDeliveryState, WatcherStateStore


RETRY_DELAYS_SECONDS = (5, 15, 30, 60, 120, 300)


@dataclass(frozen=True, slots=True)
class RuntimeSummary:
    status: str
    candidates_seen: int
    pending_stability: int
    pending_retry: int
    sent_success: int
    rejected: int
    last_error_code: str | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class WatcherRuntime:
    def __init__(
        self,
        config: WatcherConfig,
        *,
        state_store: WatcherStateStore | None = None,
        scanner: Callable[[str | Path], list[DiscoveredFile]] = scan_fiscal_pdfs,
        payload_builder: Callable[..., dict[str, object]] = build_watcher_event_payload,
        client: WatcherApiClient | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.config = config
        self._state_store = state_store or WatcherStateStore(config.state_path)
        loaded = self._state_store.load()
        self._state = loaded.state
        self._recovered_corrupt_state = loaded.recovered_corrupt_state
        self._scanner = scanner
        self._payload_builder = payload_builder
        self._client = client or WatcherApiClient(config)
        self._clock = clock
        self._started_at = _utc_now()
        self._health: dict[str, object] = {}

    def mark_starting(self) -> None:
        self._write_health_payload("STARTING")

    def run_once(self) -> RuntimeSummary:
        now = self._clock()
        try:
            discovered = self._scanner(self.config.root)
        except (OSError, FileNotFoundError):
            return self._finish("DEGRADED", 0, 0, 0, 0, 0, "ROOT_UNAVAILABLE")

        if not self._state.initialized:
            self._baseline(discovered, now)
            status = "DEGRADED" if self._recovered_corrupt_state else "RUNNING"
            error = "STATE_CORRUPT" if self._recovered_corrupt_state else None
            return self._finish(status, len(discovered), 0, 0, 0, 0, error)

        pending_stability = pending_retry = sent_success = rejected = 0
        status = "RUNNING"
        last_error: str | None = None
        for candidate in discovered:
            file_state = self._state.files.get(candidate.normalized_relative_path)
            if file_state is None:
                self._state.files[candidate.normalized_relative_path] = _observing(candidate, now)
                pending_stability += 1
                continue
            if _changed(file_state, candidate):
                self._state.files[candidate.normalized_relative_path] = _observing(candidate, now)
                pending_stability += 1
                continue
            if file_state.delivery_status == "BASELINED":
                continue
            if file_state.last_seen_sha256 and file_state.last_sent_sha256 == file_state.last_seen_sha256:
                continue
            if file_state.delivery_status == "REJECTED" and file_state.last_seen_sha256:
                continue
            if file_state.next_retry_at is not None and now < file_state.next_retry_at:
                pending_retry += 1
                continue
            if now - file_state.stable_since < self.config.stable_seconds:
                pending_stability += 1
                continue

            outcome = self._process_stable(candidate, file_state, now)
            if outcome == "SUCCESS":
                sent_success += 1
            elif outcome == "REJECTED":
                rejected += 1
            elif outcome is not None:
                pending_retry += 1
                status = "DEGRADED"
                last_error = outcome

        return self._finish(status, len(discovered), pending_stability, pending_retry, sent_success, rejected, last_error)

    def mark_stopped(self) -> None:
        self._state_store.save(self._state)
        self._write_health_payload("STOPPED")

    def stop_and_send_heartbeat(self) -> ClientResponse | None:
        """Persist a clean stop before one best-effort remote lifecycle update."""
        self.mark_stopped()
        try:
            return self.send_heartbeat()
        except Exception:  # Shutdown must not be blocked by an unavailable transport.
            return None

    def mark_fatal(self) -> None:
        self._write_health_payload("DEGRADED", last_error_code="UNEXPECTED_ERROR")

    def heartbeat_payload(self) -> dict[str, object]:
        """Return only the local health fields allowed by the server contract."""
        health = self._health
        counters = {key: int(health.get(key, 0) or 0) for key in (
            "candidates_seen", "pending_stability", "pending_retry", "sent_success", "rejected",
        )}
        return {
            "status": health.get("status", "STARTING"),
            "started_at": health.get("started_at"),
            "last_scan_at": health.get("last_scan_at"),
            "last_successful_send_at": health.get("last_successful_send_at"),
            "last_error_code": health.get("last_error_code"),
            "counters": counters,
        }

    def send_heartbeat(self) -> ClientResponse:
        return self._client.send_heartbeat(self.heartbeat_payload())

    def ingest_file(self, path: str | Path, *, confirm_send: bool) -> tuple[dict[str, object], ClientResponse | None]:
        """Handle one explicit file without invoking the polling scanner."""
        candidate = Path(path)
        payload = self._payload_builder(self.config.root, candidate, detected_at=datetime.now(timezone.utc))
        if not confirm_send:
            return payload, None
        response = self._client.send(payload)
        if response.category == "SUCCESS":
            stat = candidate.stat()
            relative_path = str(payload["relative_path"]).casefold()
            file_sha256 = str(payload["file_sha256"])
            self._state.files[relative_path] = FileDeliveryState(
                last_seen_size=stat.st_size,
                last_seen_mtime_ns=stat.st_mtime_ns,
                stable_since=self._clock(),
                last_seen_sha256=file_sha256,
                last_sent_sha256=file_sha256,
                delivery_status="SENT",
            )
            self._state.initialized = True
            self._state_store.save(self._state)
        return payload, response

    def _baseline(self, discovered: list[DiscoveredFile], now: float) -> None:
        self._state.files = {
            item.normalized_relative_path: FileDeliveryState(
                last_seen_size=item.size,
                last_seen_mtime_ns=item.mtime_ns,
                stable_since=now,
                delivery_status="BASELINED",
            )
            for item in discovered
        }
        self._state.initialized = True

    def _process_stable(self, candidate: DiscoveredFile, file_state: FileDeliveryState, now: float) -> str | None:
        try:
            payload = self._payload_builder(self.config.root, candidate.path, detected_at=datetime.now(timezone.utc))
        except PayloadBuildError as exc:
            file_state.stable_since = now
            file_state.delivery_status = "OBSERVING"
            return "FILE_CHANGED" if str(exc) == "FILE_CHANGED_DURING_PROCESSING" else "BUILD_ERROR"
        except OSError:
            file_state.stable_since = now
            file_state.delivery_status = "OBSERVING"
            return "FILE_UNAVAILABLE"

        file_sha256 = str(payload["file_sha256"])
        file_state.last_seen_sha256 = file_sha256
        if file_state.last_sent_sha256 == file_sha256:
            file_state.delivery_status = "SENT"
            file_state.retry_count = 0
            file_state.next_retry_at = None
            return "SUCCESS"

        response = self._client.send(payload)
        return self._apply_response(file_state, response, now, file_sha256)

    @staticmethod
    def _apply_response(file_state: FileDeliveryState, response: ClientResponse, now: float, file_sha256: str) -> str:
        if response.category == "SUCCESS":
            file_state.last_sent_sha256 = file_sha256
            file_state.delivery_status = "SENT"
            file_state.retry_count = 0
            file_state.next_retry_at = None
            return "SUCCESS"
        if response.category == "REJECTED":
            file_state.delivery_status = "REJECTED"
            file_state.next_retry_at = None
            return "REJECTED"
        file_state.delivery_status = "PENDING_RETRY"
        file_state.retry_count += 1
        file_state.next_retry_at = now + _retry_delay(file_state.retry_count)
        return response.category

    def _finish(
        self,
        status: str,
        candidates_seen: int,
        pending_stability: int,
        pending_retry: int,
        sent_success: int,
        rejected: int,
        last_error_code: str | None,
    ) -> RuntimeSummary:
        self._state_store.save(self._state)
        self._write_health_payload(
            status,
            candidates_seen=candidates_seen,
            pending_stability=pending_stability,
            pending_retry=pending_retry,
            sent_success=sent_success,
            rejected=rejected,
            last_error_code=last_error_code,
        )
        self._recovered_corrupt_state = False
        return RuntimeSummary(status, candidates_seen, pending_stability, pending_retry, sent_success, rejected, last_error_code)

    def _write_health_payload(
        self,
        status: str,
        *,
        candidates_seen: int | None = None,
        pending_stability: int | None = None,
        pending_retry: int | None = None,
        sent_success: int | None = None,
        rejected: int | None = None,
        last_error_code: str | None = None,
    ) -> None:
        payload = dict(self._health)
        payload["status"] = status
        payload["started_at"] = self._started_at
        if candidates_seen is not None:
            now = _utc_now()
            payload.update(
                last_scan_at=now,
                last_successful_scan_at=now if not (status == "DEGRADED" and last_error_code == "ROOT_UNAVAILABLE") else payload.get("last_successful_scan_at"),
                candidates_seen=candidates_seen,
                pending_stability=pending_stability,
                pending_retry=pending_retry,
                sent_success=sent_success,
                rejected=rejected,
                last_error_code=last_error_code,
            )
            if sent_success:
                payload["last_successful_send_at"] = now
        self._health = payload
        self._state_store.write_health(self.config.health_path, payload)


def _observing(candidate: DiscoveredFile, now: float) -> FileDeliveryState:
    return FileDeliveryState(candidate.size, candidate.mtime_ns, now)


def _changed(state: FileDeliveryState, candidate: DiscoveredFile) -> bool:
    return state.last_seen_size != candidate.size or state.last_seen_mtime_ns != candidate.mtime_ns


def _retry_delay(retry_count: int) -> int:
    return RETRY_DELAYS_SECONDS[min(max(retry_count - 1, 0), len(RETRY_DELAYS_SECONDS) - 1)]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
