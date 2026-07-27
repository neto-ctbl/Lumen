from __future__ import annotations

import subprocess
import sys

from backend.scripts.enrich_cnaes_econet import build_parser


def test_script_does_not_print_token(monkeypatch) -> None:
    monkeypatch.setenv("LUMEN_API_TOKEN", "top-secret-token")
    result = subprocess.run(
        [
            sys.executable,
            "backend/scripts/enrich_cnaes_econet.py",
            "--api-base-url",
            "http://127.0.0.1:9",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        cwd=".",
    )
    assert "top-secret-token" not in result.stdout
    assert "top-secret-token" not in result.stderr


def test_script_accepts_custom_timeout_argument() -> None:
    args = build_parser().parse_args(["--timeout-seconds", "600", "--dry-run"])
    assert args.timeout_seconds == 600
