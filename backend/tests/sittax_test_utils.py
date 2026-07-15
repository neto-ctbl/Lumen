from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "backend" / "tests" / "fixtures" / "sittax"
SCHEMAS_DIR = REPO_ROOT / "schemas"
RAW_LOG_PATH = REPO_ROOT / "scripts" / "scan" / "logs" / "sittax-network-log.jsonl"

EMAIL_RE = re.compile(r"\b[a-zA-Z0-9._%+-]+@([a-zA-Z0-9.-]+\.[A-Za-z]{2,})\b")
CNPJ_RE = re.compile(r"\b\d{14}\b")
NFE_KEY_RE = re.compile(r"\b\d{44}\b")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_fixture_paths() -> list[Path]:
    return sorted(FIXTURES_DIR.glob("*.json"))


def iter_schema_paths() -> list[Path]:
    return sorted(SCHEMAS_DIR.glob("sittax_*.schema.json"))


def canonical_json_text(path: Path) -> str:
    return json.dumps(load_json(path), ensure_ascii=True, sort_keys=True)


def run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def validate_instance(schema: dict[str, Any], instance: Any, path: str = "$") -> None:
    schema_type = schema.get("type")
    if schema_type is not None:
        allowed = schema_type if isinstance(schema_type, list) else [schema_type]
        if not any(_matches_type(item_type, instance) for item_type in allowed):
            raise AssertionError(f"{path}: invalid type")

    if instance is None:
        return

    if isinstance(instance, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                raise AssertionError(f"{path}: missing required key")

        properties = schema.get("properties", {})
        additional_properties = schema.get("additionalProperties", True)
        for key, value in instance.items():
            if key in properties:
                validate_instance(properties[key], value, f"{path}.{key}")
            elif additional_properties is False:
                raise AssertionError(f"{path}: unexpected key")
        return

    if isinstance(instance, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(instance):
                validate_instance(item_schema, item, f"{path}[{index}]")
        return


def _matches_type(expected_type: str, instance: Any) -> bool:
    if expected_type == "object":
        return isinstance(instance, dict)
    if expected_type == "array":
        return isinstance(instance, list)
    if expected_type == "string":
        return isinstance(instance, str)
    if expected_type == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if expected_type == "number":
        return (isinstance(instance, int) or isinstance(instance, float)) and not isinstance(instance, bool)
    if expected_type == "boolean":
        return isinstance(instance, bool)
    if expected_type == "null":
        return instance is None
    return True


def extract_log_sensitive_values() -> dict[str, set[str]]:
    extracted: dict[str, set[str]] = {
        "cnpj": set(),
        "email": set(),
        "office": set(),
        "ie": set(),
        "nfe_key": set(),
        "token_like": set(),
        "connection_token": set(),
    }
    if not RAW_LOG_PATH.exists():
        return extracted

    with RAW_LOG_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            _collect_sensitive(payload, extracted)
    return extracted


def _collect_sensitive(value: Any, extracted: dict[str, set[str]], parent_key: str | None = None) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            _collect_sensitive(item, extracted, key)
        return

    if isinstance(value, list):
        for item in value:
            _collect_sensitive(item, extracted, parent_key)
        return

    if not isinstance(value, str):
        return

    text = value.strip()
    if not text:
        return

    lower_parent = (parent_key or "").lower()
    for cnpj in CNPJ_RE.findall(text):
        extracted["cnpj"].add(cnpj)
    for match in EMAIL_RE.finditer(text):
        extracted["email"].add(match.group(0))
    for nfe_key in NFE_KEY_RE.findall(text):
        extracted["nfe_key"].add(nfe_key)

    if lower_parent == "escritorionome":
        extracted["office"].add(text)
    if lower_parent == "inscricaoestadual":
        extracted["ie"].add(text)
    if lower_parent == "connectiontoken":
        extracted["connection_token"].add(text)
    if lower_parent == "token":
        extracted["token_like"].add(text)
