from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "backend" / "tests" / "fixtures" / "econet"
MANIFEST_PATH = FIXTURES_DIR / "manifest.json"
RAW_LOG_PATH = REPO_ROOT / "scripts" / "scan" / "logs" / "econet-network-log.jsonl"

EMAIL_RE = re.compile(r"\b[a-zA-Z0-9._%+-]+@([a-zA-Z0-9.-]+\.[A-Za-z]{2,})\b")
CNPJ_RE = re.compile(r"\b\d{14}\b")
LONG_HEX_RE = re.compile(r"\b[a-fA-F0-9]{24,}\b")
SYNTHETIC_CNAE = "0000-0/00"
SYNTHETIC_ID = "999999"
SYNTHETIC_DESCRIPTION = "ATIVIDADE SINTETICA PARA TESTE"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_manifest() -> dict[str, Any]:
    manifest = load_json(MANIFEST_PATH)
    assert isinstance(manifest, dict), "Manifest root must be an object."
    return manifest


def iter_fixture_entries() -> list[dict[str, Any]]:
    manifest = load_manifest()
    fixtures = manifest.get("fixtures")
    assert isinstance(fixtures, list), "Manifest fixtures must be a list."
    return fixtures


def iter_fixture_paths() -> list[Path]:
    return sorted(FIXTURES_DIR.glob("*.html"))


def fixture_path(name: str) -> Path:
    return FIXTURES_DIR / name


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_html(path: Path) -> BeautifulSoup:
    return BeautifulSoup(read_text(path), "lxml")


def run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
