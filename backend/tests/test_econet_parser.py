from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.services.integrations.econet.errors import (
    EconetAuthenticationPageDetectedError,
    EconetCnaeValidationError,
    EconetUnexpectedContractError,
)
from backend.app.services.integrations.econet.parser import (
    EconetSemanticStatus,
    build_normalized_cnae_result,
    compute_content_hash,
    format_cnae,
    normalize_cnae,
    parse_cnae_detail,
    parse_empreendedor_individual,
    parse_lucro_presumido,
    parse_lucro_real_estimativa,
    parse_lucro_real_trimestral,
    parse_obligation_tabs,
    parse_obligations_general,
    parse_obligations_simei,
    parse_obligations_simples,
    parse_search_results,
    parse_simples_nacional,
)
from backend.tests.econet_test_utils import fixture_path, read_text


def test_normalize_cnae_digits() -> None:
    assert normalize_cnae("0000000") == "0000000"


def test_normalize_cnae_formatted() -> None:
    assert normalize_cnae("00.00-0-00") == "0000000"
    assert format_cnae("0000000") == "0000-0/00"


def test_normalize_cnae_rejects_invalid_length() -> None:
    with pytest.raises(EconetCnaeValidationError):
        normalize_cnae("123")


def test_parse_search_results() -> None:
    results = parse_search_results(read_text(fixture_path("search_cnae_results.html")))
    assert results[0].econet_id_cnae == "999999"
    assert results[0].cnae == "0000000"
    assert results[0].cnae_formatted == "0000-0/00"


def test_parse_search_results_multiple() -> None:
    results = parse_search_results(read_text(fixture_path("search_cnae_results.html")))
    assert len(results) == 2


def test_parse_search_result_requires_internal_id() -> None:
    html = """
    <table>
      <tr><td><label><input type="radio" name="idcnae" value="" /> 0000-0/00</label></td><td>ATIVIDADE</td></tr>
    </table>
    """
    with pytest.raises(EconetUnexpectedContractError):
        parse_search_results(html)


def test_parse_cnae_detail() -> None:
    detail = parse_cnae_detail(read_text(fixture_path("cnae_detail.html")))
    assert detail.cnae == "0000000"
    assert detail.econet_id_cnae == "999999"


def test_parse_lucro_presumido() -> None:
    result = parse_lucro_presumido(read_text(fixture_path("tax_lucro_presumido.html")))
    assert result.status == EconetSemanticStatus.ALLOWED
    assert result.allowed is True
    assert result.irpj_rate == Decimal("8")
    assert result.csll_rate == Decimal("12")


def test_parse_lucro_real_trimestral() -> None:
    result = parse_lucro_real_trimestral(read_text(fixture_path("tax_lucro_real_trimestral.html")))
    assert result.status == EconetSemanticStatus.MANDATORY
    assert result.mandatory is True


def test_parse_lucro_real_estimativa() -> None:
    result = parse_lucro_real_estimativa(read_text(fixture_path("tax_lucro_real_estimativa.html")))
    assert result.status == EconetSemanticStatus.UNKNOWN
    assert result.mandatory is None


def test_parse_simples_allowed() -> None:
    result = parse_simples_nacional(read_text(fixture_path("tax_simples_nacional.html")))
    assert result.status == EconetSemanticStatus.ALLOWED
    assert result.allowed is True
    assert result.annex_default == "III"


def test_parse_simples_prohibited() -> None:
    result = parse_simples_nacional(read_text(fixture_path("obligations_simples_prohibited.html")))
    assert result.status == EconetSemanticStatus.PROHIBITED
    assert result.allowed is False


def test_parse_simples_does_not_infer_factor_r() -> None:
    result = parse_simples_nacional(read_text(fixture_path("tax_simples_nacional.html")))
    assert result.factor_r_applicable is None
    assert result.factor_r_threshold is None
    assert result.factor_r_status == EconetSemanticStatus.NOT_OBSERVED


def test_parse_mei_allowed() -> None:
    result = parse_empreendedor_individual(read_text(fixture_path("tax_empreendedor_individual.html")))
    assert result.status == EconetSemanticStatus.ALLOWED
    assert result.allowed is True
    assert result.occupation == "OCUPACAO SINTETICA"


def test_parse_simei_not_allowed() -> None:
    result = parse_empreendedor_individual(read_text(fixture_path("obligations_simei_not_allowed.html")))
    assert result.status == EconetSemanticStatus.NOT_ALLOWED
    assert result.allowed is False


def test_parse_obligation_tabs() -> None:
    tabs = parse_obligation_tabs(read_text(fixture_path("obligations_tabs.html")))
    assert tabs.groups == ("PJ em Geral", "Optante Simples Nacional", "Optante SIMEI")


def test_parse_general_obligations() -> None:
    result = parse_obligations_general(read_text(fixture_path("obligations_pj_geral.html")))
    assert len(result.items) == 8
    assert any(item.mapped_code == "DCTFWEB" for item in result.items)


def test_parse_general_obligations_ignores_dash() -> None:
    result = parse_obligations_general(read_text(fixture_path("obligations_pj_geral.html")))
    assert all(item.name for item in result.items)


def test_parse_general_obligations_ignores_hidden_empty_rows() -> None:
    result = parse_obligations_general(read_text(fixture_path("obligations_pj_geral.html")))
    assert all("Detalhamento sintetico opcional." != item.name for item in result.items)


def test_parse_simples_prohibited_as_business_result() -> None:
    result = parse_obligations_simples(read_text(fixture_path("obligations_simples_prohibited.html")))
    assert result.status == EconetSemanticStatus.REGIME_PROHIBITED
    assert result.items == ()


def test_parse_simei_not_allowed_as_business_result() -> None:
    result = parse_obligations_simei(read_text(fixture_path("obligations_simei_not_allowed.html")))
    assert result.status == EconetSemanticStatus.REGIME_NOT_ALLOWED
    assert result.items == ()


def test_preserves_unmapped_obligations() -> None:
    result = parse_obligations_general(read_text(fixture_path("obligations_pj_geral.html")))
    assert set(result.unmapped_names) == {"DME", "DIRBI", "ECD", "ECF", "e-Social"}


def test_detects_empty_html() -> None:
    with pytest.raises(EconetUnexpectedContractError):
        parse_search_results("   ")


def test_detects_login_page() -> None:
    html = "<html><body><h1>Login</h1><form><input type='password' name='senha' /></form></body></html>"
    with pytest.raises(EconetAuthenticationPageDetectedError):
        parse_search_results(html)


def test_detects_captcha_page() -> None:
    html = "<html><body><div>captcha</div></body></html>"
    with pytest.raises(EconetAuthenticationPageDetectedError):
        parse_search_results(html)


def test_rejects_unexpected_contract() -> None:
    with pytest.raises(EconetUnexpectedContractError):
        parse_cnae_detail("<html><body><div>contrato diferente</div></body></html>")


def test_normalized_payload_is_deterministic() -> None:
    detail = parse_cnae_detail(read_text(fixture_path("cnae_detail.html")))
    payload1 = build_normalized_cnae_result(
        detail=detail,
        presumed_profit=parse_lucro_presumido(read_text(fixture_path("tax_lucro_presumido.html"))),
        actual_profit_trimestral=parse_lucro_real_trimestral(read_text(fixture_path("tax_lucro_real_trimestral.html"))),
        actual_profit_estimativa=parse_lucro_real_estimativa(read_text(fixture_path("tax_lucro_real_estimativa.html"))),
        simples=parse_simples_nacional(read_text(fixture_path("tax_simples_nacional.html"))),
        mei=parse_empreendedor_individual(read_text(fixture_path("tax_empreendedor_individual.html"))),
        obligations_general=parse_obligations_general(read_text(fixture_path("obligations_pj_geral.html"))),
        obligations_simples=parse_obligations_simples(read_text(fixture_path("obligations_simples_prohibited.html"))),
        obligations_simei=parse_obligations_simei(read_text(fixture_path("obligations_simei_not_allowed.html"))),
    )
    payload2 = build_normalized_cnae_result(
        detail=detail,
        presumed_profit=parse_lucro_presumido(read_text(fixture_path("tax_lucro_presumido.html"))),
        actual_profit_trimestral=parse_lucro_real_trimestral(read_text(fixture_path("tax_lucro_real_trimestral.html"))),
        actual_profit_estimativa=parse_lucro_real_estimativa(read_text(fixture_path("tax_lucro_real_estimativa.html"))),
        simples=parse_simples_nacional(read_text(fixture_path("tax_simples_nacional.html"))),
        mei=parse_empreendedor_individual(read_text(fixture_path("tax_empreendedor_individual.html"))),
        obligations_general=parse_obligations_general(read_text(fixture_path("obligations_pj_geral.html"))),
        obligations_simples=parse_obligations_simples(read_text(fixture_path("obligations_simples_prohibited.html"))),
        obligations_simei=parse_obligations_simei(read_text(fixture_path("obligations_simei_not_allowed.html"))),
    )
    assert payload1.normalized_payload == payload2.normalized_payload


def test_content_hash_is_deterministic() -> None:
    payload = {
        "b": 2,
        "a": {"d": "1.00", "c": None},
    }
    assert compute_content_hash(payload) == compute_content_hash({"a": {"c": None, "d": "1.00"}, "b": 2})
