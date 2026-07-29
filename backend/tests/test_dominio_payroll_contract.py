from __future__ import annotations

from backend.app.services.integrations.dominio.contracts import (
    DominioDocumentContract,
    DominioEvidenceSource,
    DominioSelectionScope,
)
from backend.tests.dominio_test_utils import (
    CNPJ_RE,
    FIXTURES_DIR,
    PASSWORD_RE,
    TOKEN_RE,
    load_manifest,
    load_samples,
)


EXPECTED_SCENARIOS = {
    "ONLY_PRO_LABORE",
    "EMPLOYEE_INSS_FGTS",
    "AUTONOMOUS",
    "VACATION",
    "TERMINATION",
    "LEAVE",
    "TWO_PAGES",
    "EMPTY_CONTINUATION_PAGE",
    "SALARY_CHANGE",
    "MULTIPLE_BLOCKS",
    "INVALID_CNPJ",
    "INVALID_PAYROLL_COMPETENCE",
    "PAYROLL_2026_05_TO_2026_06",
    "PAYROLL_2026_12_TO_2027_01",
}

ALLOWED_CNPJS = {
    "12345678000195",
    "22345678000195",
    "32345678000195",
    "42345678000195",
    "52345678000195",
    "62345678000195",
    "72345678000195",
    "82345678000195",
    "92345678000195",
    "11345678000195",
    "13345678000195",
    "14345678000195",
    "15345678000195",
}


def test_contract_enums_match_expected_canonical_values() -> None:
    assert DominioDocumentContract.DOMINIO_FOLHA_RESUMO.value == "DOMINIO_FOLHA_RESUMO"
    assert DominioEvidenceSource.DOMINIO_FOLHA_PDF.value == "DOMINIO_FOLHA_PDF"
    assert DominioSelectionScope.ATIVAS.value == "ATIVAS"


def test_fixture_manifest_and_samples_exist() -> None:
    assert FIXTURES_DIR.exists()
    manifest = load_manifest()
    samples = load_samples()
    assert manifest["contract_version"] == "s9.0"
    assert manifest["network_access_required"] is False
    assert manifest["synthetic_only"] is True
    assert samples["document_contract"] == "DOMINIO_FOLHA_RESUMO"
    assert samples["evidence_source"] == "DOMINIO_FOLHA_PDF"
    assert samples["selection_scope"] == "ATIVAS"


def test_all_expected_scenarios_are_covered_once() -> None:
    manifest = load_manifest()
    samples = load_samples()
    scenarios = {entry["scenario"] for entry in samples["fixtures"]}
    assert scenarios == EXPECTED_SCENARIOS
    assert set(manifest["scenarios"]) == EXPECTED_SCENARIOS
    assert len(samples["fixtures"]) == len(EXPECTED_SCENARIOS)


def test_mapping_examples_are_frozen_in_fixtures() -> None:
    samples = load_samples()
    by_name = {entry["scenario"]: entry for entry in samples["fixtures"]}
    assert by_name["PAYROLL_2026_05_TO_2026_06"]["source_payroll_competence"] == "2026-05"
    assert by_name["PAYROLL_2026_05_TO_2026_06"]["assessment_competence"] == "2026-06"
    assert by_name["PAYROLL_2026_12_TO_2027_01"]["source_payroll_competence"] == "2026-12"
    assert by_name["PAYROLL_2026_12_TO_2027_01"]["assessment_competence"] == "2027-01"


def test_fixtures_do_not_contain_obvious_real_markers_or_secrets() -> None:
    blob = (FIXTURES_DIR / "manifest.json").read_text(encoding="utf-8")
    blob += "\n" + (FIXTURES_DIR / "synthetic_contract_samples.json").read_text(encoding="utf-8")
    assert "NETO CONTABILIDADE" not in blob
    assert "DOMINIO_PASSWORD" not in blob
    assert "ALTERE_LOCALMENTE" not in blob
    assert PASSWORD_RE.search(blob) is None
    assert TOKEN_RE.search(blob) is None


def test_fixtures_use_only_expected_synthetic_cnpjs() -> None:
    blob = (FIXTURES_DIR / "synthetic_contract_samples.json").read_text(encoding="utf-8")
    cnpjs = set(CNPJ_RE.findall(blob))
    assert cnpjs <= ALLOWED_CNPJS
