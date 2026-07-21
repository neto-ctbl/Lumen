from __future__ import annotations

from backend.tests.econet_test_utils import (
    FIXTURES_DIR,
    SYNTHETIC_CNAE,
    SYNTHETIC_DESCRIPTION,
    SYNTHETIC_ID,
    iter_fixture_entries,
    load_manifest,
    parse_html,
)


EXPECTED_SCENARIOS = {
    "SEARCH_RESULTS",
    "CNAE_DETAIL",
    "TAX_LUCRO_PRESUMIDO",
    "TAX_LUCRO_REAL_TRIMESTRAL",
    "TAX_LUCRO_REAL_ESTIMATIVA",
    "TAX_SIMPLES_NACIONAL",
    "TAX_EMPREENDEDOR_INDIVIDUAL",
    "OBLIGATIONS_TABS",
    "OBLIGATIONS_PJ_GERAL",
    "OBLIGATIONS_SIMPLES_PROHIBITED",
    "OBLIGATIONS_SIMEI_NOT_ALLOWED",
}


def test_manifest_is_valid_and_has_no_duplicate_fixture_names() -> None:
    manifest = load_manifest()
    assert manifest["contract_version"] == "s8.0"
    names = [entry["file"] for entry in iter_fixture_entries()]
    assert len(names) == len(set(names))


def test_expected_scenarios_are_covered() -> None:
    scenarios = {entry["scenario"] for entry in iter_fixture_entries()}
    assert scenarios == EXPECTED_SCENARIOS


def test_all_html_fixtures_are_parseable_without_javascript() -> None:
    for entry in iter_fixture_entries():
        soup = parse_html(FIXTURES_DIR / entry["file"])
        assert soup.find() is not None, f"{entry['file']}: expected parseable HTML"


def test_search_fixture_contains_synthetic_result_and_internal_id() -> None:
    soup = parse_html(FIXTURES_DIR / "search_cnae_results.html")
    radio = soup.find("input", {"name": "idcnae", "value": SYNTHETIC_ID})
    assert radio is not None
    assert SYNTHETIC_CNAE in soup.get_text(" ", strip=True)
    assert SYNTHETIC_DESCRIPTION in soup.get_text(" ", strip=True)


def test_cnae_detail_contains_synthetic_identity_markers() -> None:
    soup = parse_html(FIXTURES_DIR / "cnae_detail.html")
    text = soup.get_text(" ", strip=True)
    assert SYNTHETIC_CNAE in text
    assert SYNTHETIC_DESCRIPTION in text
    assert soup.find(attrs={"data-econet-id": SYNTHETIC_ID}) is not None


def test_tax_fixtures_contain_expected_tab_markers() -> None:
    expected_markers = {
        "tax_lucro_presumido.html": "Lucro Presumido",
        "tax_lucro_real_trimestral.html": "Lucro Real Trimestral",
        "tax_lucro_real_estimativa.html": "Lucro Real por Estimativa",
        "tax_simples_nacional.html": "Simples Nacional",
        "tax_empreendedor_individual.html": "Empreendedor Individual",
    }
    for file_name, marker in expected_markers.items():
        soup = parse_html(FIXTURES_DIR / file_name)
        assert marker in soup.get_text(" ", strip=True)


def test_obligations_tabs_contains_expected_groups() -> None:
    soup = parse_html(FIXTURES_DIR / "obligations_tabs.html")
    text = soup.get_text(" ", strip=True)
    assert "PJ em Geral" in text
    assert "Optante Simples Nacional" in text
    assert "Optante SIMEI" in text


def test_obligations_pj_geral_contains_valid_list_shape() -> None:
    soup = parse_html(FIXTURES_DIR / "obligations_pj_geral.html")
    table = soup.find("table", {"class": "tabelaResultados"})
    assert table is not None
    text = soup.get_text(" ", strip=True)
    for obligation in ["DCTFWeb", "EFD-Contribuicoes", "EFD-Reinf", "DME", "e-Social", "ECD", "ECF", "DIRBI"]:
        assert obligation in text


def test_negative_business_messages_are_treated_as_valid_contract_outputs() -> None:
    simples = parse_html(FIXTURES_DIR / "obligations_simples_prohibited.html").get_text(" ", strip=True)
    simei = parse_html(FIXTURES_DIR / "obligations_simei_not_allowed.html").get_text(" ", strip=True)
    assert "impedida ao Simples Nacional" in simples
    assert "nao e possivel o enquadramento como Microempreendedor Individual" in simei
