from __future__ import annotations

from backend.tests.econet_test_utils import (
    CNPJ_RE,
    EMAIL_RE,
    FIXTURES_DIR,
    LONG_HEX_RE,
    SYNTHETIC_CNAE,
    SYNTHETIC_DESCRIPTION,
    SYNTHETIC_ID,
    iter_fixture_entries,
    iter_fixture_paths,
    load_manifest,
    read_text,
)


BANNED_SUBSTRINGS = [
    "Authorization:",
    "Bearer ",
    "Cookie:",
    "PHPSESSID=",
    "_grecaptcha",
    "econet-network.har",
    "econet-network-log.jsonl",
    "econet-storage-before.json",
    "econet-storage-after.json",
    "econet-storage-diff.json",
    "NETO CONTABILIDADE",
]

ALLOWED_CNPJS = {"12345678000195"}


def test_manifest_references_existing_fixture_files() -> None:
    for entry in iter_fixture_entries():
        fixture_path = FIXTURES_DIR / entry["file"]
        assert fixture_path.exists(), f"Fixture listed in manifest is missing: {entry['file']}"


def test_fixtures_do_not_contain_sensitive_markers() -> None:
    for path in iter_fixture_paths():
        text = read_text(path)
        for marker in BANNED_SUBSTRINGS:
            assert marker not in text, f"{path.name}: banned marker detected"
        assert "token" not in text.lower(), f"{path.name}: token marker detected"


def test_fixtures_do_not_contain_long_hex_like_tokens() -> None:
    for path in iter_fixture_paths():
        matches = LONG_HEX_RE.findall(read_text(path))
        assert not matches, f"{path.name}: long hex-like token detected"


def test_fixtures_do_not_contain_real_emails_or_unknown_cnpjs() -> None:
    for path in iter_fixture_paths():
        text = read_text(path)
        assert not EMAIL_RE.search(text), f"{path.name}: email detected"
        cnpjs = set(CNPJ_RE.findall(text))
        assert cnpjs <= ALLOWED_CNPJS, f"{path.name}: unexpected CNPJ detected"


def test_fixtures_use_expected_synthetic_business_markers() -> None:
    fixture_blob = "\n".join(read_text(path) for path in iter_fixture_paths())
    assert SYNTHETIC_ID in fixture_blob
    assert SYNTHETIC_CNAE in fixture_blob
    assert SYNTHETIC_DESCRIPTION in fixture_blob


def test_fixtures_are_utf8_and_without_scripts() -> None:
    for path in iter_fixture_paths():
        text = read_text(path)
        assert "<script" not in text.lower(), f"{path.name}: script tag detected"


def test_manifest_declares_offline_usage_and_synthetic_fixtures() -> None:
    manifest = load_manifest()
    assert manifest["network_access_required"] is False
    for entry in manifest["fixtures"]:
        assert entry["synthetic"] is True
