from __future__ import annotations

from backend.tests.sittax_test_utils import (
    CNPJ_RE,
    EMAIL_RE,
    NFE_KEY_RE,
    RAW_LOG_PATH,
    canonical_json_text,
    extract_log_sensitive_values,
    iter_fixture_paths,
    load_json,
    run_git,
)


MAX_FIXTURE_BYTES = 32_000
BANNED_SUBSTRINGS = [
    "Authorization",
    "Bearer ",
    "connectionToken",
    "apiKeyAcessorias",
]


def test_all_sittax_fixtures_are_valid_json_and_small() -> None:
    fixture_paths = iter_fixture_paths()
    assert fixture_paths, "Expected Sittax fixtures to exist."
    for path in fixture_paths:
        load_json(path)
        assert path.stat().st_size <= MAX_FIXTURE_BYTES, f"{path.name}: fixture exceeds size budget"


def test_fixtures_do_not_contain_banned_sensitive_markers() -> None:
    for path in iter_fixture_paths():
        text = canonical_json_text(path)
        for marker in BANNED_SUBSTRINGS:
            assert marker not in text, f"{path.name}: sensitive marker detected"
        assert "password" not in text.lower(), f"{path.name}: password marker detected"
        assert "cookie" not in text.lower(), f"{path.name}: cookie marker detected"


def test_fixture_emails_use_invalid_domain_only() -> None:
    all_domains: set[str] = set()
    for path in iter_fixture_paths():
        text = canonical_json_text(path)
        domains = {match.group(1).lower() for match in EMAIL_RE.finditer(text)}
        all_domains.update(domains)
        assert all(domain.endswith(".invalid") for domain in domains), f"{path.name}: non-invalid email domain found"
    assert all_domains, "Expected at least one synthetic email across Sittax fixtures."


def test_fixtures_do_not_reuse_sensitive_values_from_raw_log() -> None:
    log_values = extract_log_sensitive_values()
    fixture_blob = "\n".join(canonical_json_text(path) for path in iter_fixture_paths())
    for value in log_values["cnpj"] | log_values["email"] | log_values["office"] | log_values["ie"] | log_values["nfe_key"]:
        if value:
            assert value not in fixture_blob, "A sensitive value extracted from the private Sittax log leaked into fixtures."
    for value in log_values["token_like"] | log_values["connection_token"]:
        if value:
            assert value not in fixture_blob, "A token-like value extracted from the private Sittax log leaked into fixtures."


def test_fixtures_use_expected_synthetic_business_markers() -> None:
    fixture_blob = "\n".join(canonical_json_text(path) for path in iter_fixture_paths())
    assert "EMPRESA EXEMPLO A" in fixture_blob
    assert "ESCRITORIO EXEMPLO" in fixture_blob
    assert "USUARIO EXEMPLO" in fixture_blob
    assert "example.invalid" in fixture_blob
    assert "12345678000195" in fixture_blob
    assert "98765432000110" in fixture_blob


def test_raw_log_file_is_ignored_and_not_tracked() -> None:
    assert RAW_LOG_PATH.exists(), "Expected the private Sittax network log to exist for local analysis."
    ignored = run_git("check-ignore", "-v", str(RAW_LOG_PATH))
    assert ignored.returncode == 0, "Expected the private Sittax network log to be ignored by Git."

    tracked = run_git("ls-files")
    assert tracked.returncode == 0
    assert "sittax-network-log" not in tracked.stdout


def test_fixtures_do_not_embed_44_digit_nfe_or_private_cnpjs_from_log() -> None:
    fixture_blob = "\n".join(canonical_json_text(path) for path in iter_fixture_paths())
    nfe_keys = set(NFE_KEY_RE.findall(fixture_blob))
    cnpjs = set(CNPJ_RE.findall(fixture_blob))
    assert all(key.startswith("2026") is False for key in nfe_keys), "Unexpected production-like NFe key found in fixtures."
    assert "12345678000195" in cnpjs
    assert "98765432000110" in cnpjs
