"""CLI entry point for the polling fiscal watcher."""

from __future__ import annotations

import argparse
import json
import time

from agent.watcher.config import WatcherConfig
from agent.watcher.runtime import WatcherRuntime
from agent.watcher.state import WatcherStateStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lumen fiscal watcher agent")
    parser.add_argument("--once", action="store_true", help="run one polling cycle without bypassing stability")
    parser.add_argument("--status", action="store_true", help="print sanitized local health only")
    parser.add_argument("--ingest-file", help="explicit single PDF path; never scans a directory")
    parser.add_argument("--confirm-send", action="store_true", help="allow network send for --ingest-file")
    args = parser.parse_args(argv)
    config = WatcherConfig.from_env()
    if args.status:
        print(json.dumps(_read_health(config.health_path), ensure_ascii=True, sort_keys=True))
        return 0

    runtime = WatcherRuntime(config)
    runtime.mark_starting()
    try:
        if args.ingest_file:
            exit_code = _manual_ingest(runtime, args.ingest_file, args.confirm_send)
            runtime.stop_and_send_heartbeat()
            return exit_code
        if args.once:
            summary = runtime.run_once()
            print(json.dumps(summary.to_dict(), ensure_ascii=True, sort_keys=True))
            runtime.send_heartbeat()
            runtime.stop_and_send_heartbeat()
            return 0
        while True:
            print(json.dumps(runtime.run_once().to_dict(), ensure_ascii=True, sort_keys=True))
            runtime.send_heartbeat()
            time.sleep(config.scan_interval_seconds)
    except KeyboardInterrupt:
        runtime.stop_and_send_heartbeat()
        return 0
    except Exception:
        runtime.mark_fatal()
        raise


def _read_health(path: object) -> dict[str, object]:
    try:
        raw = json.loads(WatcherStateStore(path).path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {"status": "STOPPED"}
    allowed = {
        "status", "started_at", "last_scan_at", "last_successful_scan_at", "last_successful_send_at",
        "candidates_seen", "pending_stability", "pending_retry", "sent_success", "rejected", "last_error_code",
    }
    return {key: value for key, value in raw.items() if key in allowed}


def _manual_ingest(runtime: WatcherRuntime, value: str, confirm_send: bool) -> int:
    from agent.watcher.payload_builder import PayloadBuildError

    try:
        payload, response = runtime.ingest_file(value, confirm_send=confirm_send)
    except (PayloadBuildError, OSError) as exc:
        print(json.dumps({"status": "REJECTED", "error_code": str(exc)}, ensure_ascii=True, sort_keys=True))
        return 2
    if response is None:
        print(json.dumps({"status": "DRY_RUN_VALID", "file_sha256": payload["file_sha256"]}, ensure_ascii=True, sort_keys=True))
        return 0
    print(json.dumps({"status": response.category, "status_code": response.status_code}, ensure_ascii=True, sort_keys=True))
    return 0 if response.category == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
