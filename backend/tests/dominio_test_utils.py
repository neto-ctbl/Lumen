from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "backend" / "tests" / "fixtures" / "dominio"
MANIFEST_PATH = FIXTURES_DIR / "manifest.json"
SCENARIOS_PATH = FIXTURES_DIR / "synthetic_contract_samples.json"

CNPJ_RE = re.compile(r"\b\d{14}\b")
PASSWORD_RE = re.compile(r"password\s*=", flags=re.IGNORECASE)
TOKEN_RE = re.compile(r"\b(token|authorization|bearer|cookie)\b", flags=re.IGNORECASE)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_manifest() -> dict[str, Any]:
    manifest = load_json(MANIFEST_PATH)
    assert isinstance(manifest, dict)
    return manifest


def load_samples() -> dict[str, Any]:
    samples = load_json(SCENARIOS_PATH)
    assert isinstance(samples, dict)
    return samples
