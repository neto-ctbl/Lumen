from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path

import pytest

from agent.parsers.contracts import (
    DocumentContext,
    DocumentSignal,
    ExtractionStatus,
    SignalProvenance,
    TechnicalFormat,
)
from agent.parsers.mit_json import (
    MIT_JSON_LAYOUT_ID,
    MIT_JSON_PARSER_NAME,
    MIT_JSON_PARSER_VERSION,
    MitDocument,
    MitDebitListKind,
    MitJsonLayoutExtractor,
    MitPeriodKind,
    sanitized_mit_json_probe,
)
from agent.parsers.mit_revenue_codes import (
    MIT_REVENUE_CATALOG_EXPECTED_COUNT,
    MIT_REVENUE_CODES,
    lookup_mit_revenue_code,
)
from agent.parsers.runtime import DocumentParserRuntime, default_parser_registry


def _payload(*groups: str, period: dict[str, int] | None = None) -> dict[str, object]:
    codes = {
        "Irpj": "022001",
        "Csll": "203001",
        "Irrf": "776901",
        "Ipi": "066803",
        "Iof": "115002",
        "PisPasep": "810902",
        "Cofins": "217201",
        "ContribuicoesDiversas": "874101",
        "Cpss": "178102",
        "RetPagamentoUnificado": "106801",
    }
    debit_groups: dict[str, object] = {}
    for index, group in enumerate(groups, start=1):
        debit_groups[group] = {
            "ListaDebitos": [
                {
                    "IdDebito": index,
                    "CodigoDebito": codes.get(group, "810902"),
                    "ValorDebito": index,
                }
            ]
        }
    return {
        "PeriodoApuracao": (
            {"MesApuracao": 6, "AnoApuracao": 2026} if period is None else period
        ),
        "DadosIniciais": {
            "SemMovimento": False,
            "QualificacaoPj": 1,
            "TributacaoLucro": 2,
            "VariacoesMonetarias": 3,
            "ResponsavelApuracao": {
                "CpfResponsavel": "11144477735",
                "TelResponsavel": {"Ddd": "00", "NumTelefone": "000000000"},
                "EmailResponsavel": "synthetic@example.invalid",
                "RegistroCrc": {"UfRegistro": "GO", "NumRegistro": "SYNTHETIC"},
            },
        },
        "Debitos": debit_groups,
    }


def _write(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _run(path: Path, *, signals: tuple[DocumentSignal, ...] = ()):
    return DocumentParserRuntime(default_parser_registry()).run_file(path, context_signals=signals)


def _document(result: object) -> MitDocument:
    return MitDocument.model_validate(result.structured_data)  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("group", "tax"),
    (("PisPasep", "PIS"), ("Cofins", "COFINS"), ("Irpj", "IRPJ"), ("Csll", "CSLL")),
)
def test_mit_known_tax_groups_are_normalized(tmp_path: Path, group: str, tax: str) -> None:
    result = _run(_write(tmp_path / "importacao.json", _payload(group)))

    assert result.parser_name == MIT_JSON_PARSER_NAME
    assert result.parser_version == MIT_JSON_PARSER_VERSION
    assert result.document_family == "MIT"
    assert result.extraction_status is ExtractionStatus.MATCHED
    document = _document(result)
    assert document.layout_id == MIT_JSON_LAYOUT_ID
    assert [(debit.raw_group, debit.tax) for debit in document.debits] == [(group, tax)]


def test_mit_supports_multiple_groups_and_debits_in_one_group(tmp_path: Path) -> None:
    payload = _payload("PisPasep", "Cofins", "Irpj", "Csll")
    payload["Debitos"]["PisPasep"]["ListaDebitos"].append(  # type: ignore[index]
        {"IdDebito": 99, "CodigoDebito": "810902", "ValorDebito": 0}
    )
    document = _document(_run(_write(tmp_path / "neutral.json", payload)))

    assert len(document.debits) == 5
    assert {debit.tax for debit in document.debits} == {"PIS", "COFINS", "IRPJ", "CSLL"}
    assert next(debit for debit in document.debits if debit.identifiers.debit_id == "99").principal == 0


def test_decimal_numbers_are_never_rounded_through_float(tmp_path: Path) -> None:
    path = tmp_path / "precision.json"
    path.write_text(
        '{"PeriodoApuracao":{"MesApuracao":6,"AnoApuracao":2026},'
        '"DadosIniciais":{"SemMovimento":false,"QualificacaoPj":1},'
        '"Debitos":{"PisPasep":{"ListaDebitos":[{"IdDebito":1,'
        '"CodigoDebito":"810902","ValorDebito":0.123456789012345678901}]}}}',
        encoding="utf-8",
    )

    result = _run(path)
    document = _document(result)
    assert str(document.debits[0].principal) == "0.123456789012345678901"
    assert result.structured_data["debits"][0]["principal"] == "0.123456789012345678901"  # type: ignore[index]


def test_monthly_file_period_and_explicit_quarterly_debit_period_are_separate(
    tmp_path: Path,
) -> None:
    payload = _payload("Irpj")
    payload["Debitos"]["Irpj"]["ListaDebitos"][0].update(  # type: ignore[index]
        {"AnoPostergado": 2025, "TrimPostergado": 2}
    )
    result = _run(_write(tmp_path / "quarter.json", payload))
    document = _document(result)

    assert document.assessment_period is not None
    assert document.assessment_period.kind is MitPeriodKind.MONTH
    assert document.debits[0].assessment_period is not None
    assert document.debits[0].assessment_period.kind is MitPeriodKind.QUARTER
    assert document.debits[0].assessment_period.period == "2025-Q2"
    assert document.debits[0].postponed_year == 2025
    assert document.debits[0].postponed_quarter == 2
    assert result.warnings == ()


def test_unknown_group_is_preserved_without_failing_document(tmp_path: Path) -> None:
    result = _run(_write(tmp_path / "importacao.json", _payload("NovoGrupo")))
    document = _document(result)

    assert result.extraction_status is ExtractionStatus.MATCHED
    assert document.debits[0].tax == "UNKNOWN"
    assert document.debits[0].raw_group == "NovoGrupo"
    assert document.validation.unknown_debit_groups_count == 1
    assert result.warnings == ("MIT_UNKNOWN_DEBIT_GROUP",)


def test_invalid_balance_field_is_inconclusive(tmp_path: Path) -> None:
    payload = _payload("PisPasep", "Cofins")
    payload["Debitos"]["BalancoLucroReal"] = {}  # type: ignore[index]

    result = _run(_write(tmp_path / "empty-section.json", payload))
    assert result.extraction_status is ExtractionStatus.INCONCLUSIVE
    assert result.document_family == "UNKNOWN"
    assert result.warnings == ("MIT_STRUCTURE_INCONCLUSIVE",)


def test_balance_reduction_or_suspension_is_a_typed_known_field(tmp_path: Path) -> None:
    payload = _payload("PisPasep", "Cofins")
    payload["Debitos"]["BalancoLucroReal"] = False  # type: ignore[index]

    result = _run(_write(tmp_path / "scalar-field.json", payload))
    document = _document(result)

    assert result.extraction_status is ExtractionStatus.MATCHED
    assert len(document.debits) == 2
    assert {debit.tax for debit in document.debits} == {"PIS", "COFINS"}
    assert document.balance_reduction_or_suspension is False
    assert document.unknown_debits_fields == ()
    assert document.validation.unknown_debit_groups_count == 0
    assert result.warnings == ()


def test_optional_field_absence_and_noncritical_extra_keys_are_controlled(tmp_path: Path) -> None:
    payload = _payload("PisPasep")
    del payload["DadosIniciais"]["ResponsavelApuracao"]  # type: ignore[index]
    payload["NovaChaveVersao"] = {"ignored": "synthetic"}
    payload["DadosIniciais"]["NovaFlag"] = True  # type: ignore[index]
    payload["Debitos"]["PisPasep"]["ListaDebitos"][0]["NovoCampo"] = "synthetic"  # type: ignore[index]
    document = _document(_run(_write(tmp_path / "extra.json", payload)))

    assert document.initial_data.assessment_responsible is None
    assert document.unknown_top_level_fields == ("NovaChaveVersao",)
    assert document.initial_data.unknown_fields == ("NovaFlag",)
    assert document.debits[0].unknown_fields == ("NovoCampo",)
    assert "ignored" not in document.model_dump_json()


def test_official_schema_optional_sections_and_all_debit_groups_are_typed(
    tmp_path: Path,
) -> None:
    groups = (
        "Irpj",
        "Csll",
        "Irrf",
        "Ipi",
        "Iof",
        "PisPasep",
        "Cofins",
        "ContribuicoesDiversas",
        "Cpss",
        "RetPagamentoUnificado",
    )
    payload = _payload(*groups)
    payload["DadosIniciais"]["RegimePisCofins"] = 1  # type: ignore[index]
    payload["ListaEventosEspeciais"] = [
        {"IdEvento": 1, "DiaEvento": 15, "TipoEvento": 2}
    ]
    payload["Debitos"]["BalancoLucroReal"] = True  # type: ignore[index]
    payload["Debitos"]["Irpj"]["ListaDebitosAposEvento"] = [  # type: ignore[index]
        {
            "IdDebito": 50,
            "CodigoDebito": "775603",
            "AnoDebito": 2025,
            "CnpjScp": "00000000000000",
            "ValorDebito": "10.010",
        }
    ]
    payload["Debitos"]["Iof"]["ListaDebitos"][0].update(  # type: ignore[index]
        {"PaDebito": 2, "CodigoMunicipioOuro": "0000000"}
    )
    payload["Debitos"]["Ipi"]["ListaDebitos"][0][  # type: ignore[index]
        "CnpjEstabelecimento"
    ] = "00000000000000"
    payload["Debitos"]["RetPagamentoUnificado"]["ListaDebitos"][0][  # type: ignore[index]
        "CnpjIncorporacao"
    ] = "00000000000000"
    payload["ListaSuspensoes"] = [
        {
            "TipoSuspensao": 1,
            "MotivoSuspensao": 2,
            "ComDeposito": False,
            "NumeroProcesso": "SYNTHETIC",
            "ProcessoTerceiro": False,
            "DataDecisao": 20260101,
            "VaraJudiciaria": 1,
            "CodigoMunicipioSj": "0000000",
            "ListaDebitosSuspensos": [
                {"IdDebitoSuspenso": 1, "ValorSuspenso": "0.001"}
            ],
        }
    ]

    result = _run(_write(tmp_path / "official-schema.json", payload))
    document = _document(result)

    assert result.extraction_status is ExtractionStatus.MATCHED
    assert result.warnings == ()
    assert document.initial_data.pis_cofins_regime == 1
    assert document.balance_reduction_or_suspension is True
    assert len(document.special_events) == 1
    assert len(document.debits) == 11
    assert {debit.tax for debit in document.debits} == {
        "IRPJ",
        "CSLL",
        "IRRF",
        "IPI",
        "IOF",
        "PIS",
        "COFINS",
        "CONTRIBUICOES_DIVERSAS",
        "CPSS",
        "RET_PAGAMENTO_UNIFICADO",
    }
    after_event = next(
        debit for debit in document.debits if debit.list_kind is MitDebitListKind.AFTER_EVENT
    )
    assert after_event.assessment_period is not None
    assert after_event.assessment_period.kind is MitPeriodKind.YEAR
    assert after_event.principal == Decimal("10.010")
    assert document.suspensions[0].suspended_debits[0].suspended_amount == Decimal(
        "0.001"
    )


def test_revenue_catalog_has_all_official_codes_and_enriches_without_gating() -> None:
    assert len(MIT_REVENUE_CODES) == MIT_REVENUE_CATALOG_EXPECTED_COUNT == 240
    assert lookup_mit_revenue_code("0220-01").group == "IRPJ"  # type: ignore[union-attr]
    assert lookup_mit_revenue_code("810902").periodicity == "ME"  # type: ignore[union-attr]
    assert lookup_mit_revenue_code("6177-01").group == "RET_PAGAMENTO_UNIFICADO"  # type: ignore[union-attr]


def test_new_revenue_code_is_preserved_with_sanitized_warning(tmp_path: Path) -> None:
    payload = _payload("PisPasep")
    payload["Debitos"]["PisPasep"]["ListaDebitos"][0][  # type: ignore[index]
        "CodigoDebito"
    ] = "999999"

    result = _run(_write(tmp_path / "future-code.json", payload))
    debit = _document(result).debits[0]

    assert result.extraction_status is ExtractionStatus.MATCHED
    assert debit.revenue_code == "999999"
    assert debit.revenue_code_catalog_known is False
    assert result.warnings == ("MIT_REVENUE_CODE_UNKNOWN",)
    assert "999999" not in result.warnings


def test_incomplete_postponed_quarter_emits_debit_period_warning(tmp_path: Path) -> None:
    payload = _payload("Irpj")
    payload["Debitos"]["Irpj"]["ListaDebitos"][0][  # type: ignore[index]
        "AnoPostergado"
    ] = 2025

    result = _run(_write(tmp_path / "incomplete-period.json", payload))

    assert result.extraction_status is ExtractionStatus.MATCHED
    assert _document(result).debits[0].assessment_period is None
    assert result.warnings == ("MIT_DEBIT_PERIOD_MISSING",)


def test_missing_period_and_no_debits_are_document_warnings(tmp_path: Path) -> None:
    payload = _payload(period={})
    result = _run(_write(tmp_path / "empty-mit.json", payload))
    document = _document(result)

    assert result.extraction_status is ExtractionStatus.MATCHED
    assert document.assessment_period is None and document.debits == ()
    assert result.warnings == ("MIT_ASSESSMENT_PERIOD_MISSING", "MIT_NO_DEBITS")


def test_no_activity_mit_may_omit_debits_property(tmp_path: Path) -> None:
    payload = _payload()
    payload["DadosIniciais"]["SemMovimento"] = True  # type: ignore[index]
    del payload["Debitos"]

    result = _run(_write(tmp_path / "no-activity.json", payload))
    document = _document(result)

    assert result.extraction_status is ExtractionStatus.MATCHED
    assert document.initial_data.no_activity is True
    assert document.debits == ()
    assert document.validation.debit_count == 0
    assert result.warnings == ("MIT_NO_DEBITS",)


def test_missing_debits_is_not_accepted_for_active_document(tmp_path: Path) -> None:
    payload = _payload()
    del payload["Debitos"]

    result = _run(_write(tmp_path / "active-without-debits.json", payload))

    assert result.extraction_status is ExtractionStatus.UNSUPPORTED
    assert result.document_family == "UNKNOWN"
    assert result.warnings == ("UNKNOWN_JSON_LAYOUT",)


@pytest.mark.parametrize(
    "payload",
    (
        {},
        {"generic": True},
        {"PeriodoApuracao": {"MesApuracao": 6, "AnoApuracao": 2026}},
        {"PeriodoApuracao": {}, "DadosIniciais": {}, "Debitos": {}},
        {"system": "other", "records": []},
    ),
)
def test_valid_non_mit_json_is_unknown_and_unsupported(tmp_path: Path, payload: object) -> None:
    result = _run(_write(tmp_path / "MIT-enganoso.json", payload))

    assert result.extraction_status is ExtractionStatus.UNSUPPORTED
    assert result.document_family == "UNKNOWN"
    assert result.warnings == ("UNKNOWN_JSON_LAYOUT",)
    assert {signal.value for signal in result.signals if signal.name == "layout_id"} == {"UNKNOWN"}


def test_malformed_json_is_invalid_and_sanitized(tmp_path: Path) -> None:
    path = tmp_path / "MIT.json"
    path.write_text('{"PeriodoApuracao":', encoding="utf-8")

    result = _run(path)
    assert result.extraction_status is ExtractionStatus.INVALID
    assert result.warnings == ("MIT_JSON_INVALID",)
    assert result.structured_data == {}


def test_filename_is_not_needed_and_path_period_cannot_override_content(tmp_path: Path) -> None:
    path_hint = DocumentSignal(
        name="period_from_path",
        value="2025-01",
        provenance=SignalProvenance.PATH,
        confidence=0.2,
    )
    result = _run(
        _write(tmp_path / "completely-neutral.json", _payload("Cofins")),
        signals=(path_hint,),
    )
    periods = {(signal.name, signal.value, signal.provenance) for signal in result.signals}

    assert result.document_family == "MIT"
    assert ("period_from_content", "2026-06", SignalProvenance.CONTENT) in periods
    assert ("period_from_path", "2025-01", SignalProvenance.PATH) in periods
    assert result.warnings == ("MIT_PERIOD_CONFLICT",)


def test_json_framework_pipeline_and_default_registries_need_no_runtime_change(
    tmp_path: Path,
) -> None:
    path = _write(tmp_path / "framework.json", _payload("PisPasep"))
    context = DocumentContext(file_path=path, technical_format=TechnicalFormat.JSON)
    extractor = MitJsonLayoutExtractor()

    assert extractor.supports_layout(context) is True
    result = _run(path)
    signals = {signal.name: signal for signal in result.signals}
    assert signals["technical_format"].value == "JSON"
    assert signals["layout_id"].value == MIT_JSON_LAYOUT_ID
    assert signals["layout_id"].provenance is SignalProvenance.FILE_STRUCTURE
    assert signals["classification_id"].value == "MIT"
    assert signals["mit_structure_recognized"].provenance is SignalProvenance.FILE_STRUCTURE
    assert any(parser.name == MIT_JSON_PARSER_NAME for parser in default_parser_registry().parsers_for(TechnicalFormat.JSON))


def test_probe_is_allowlisted_and_does_not_expose_source_data(tmp_path: Path) -> None:
    path = _write(tmp_path / "sensitive-company-MIT.json", _payload("PisPasep", "Cofins"))
    probe = sanitized_mit_json_probe(path)
    serialized = probe.model_dump_json()

    assert probe.family == "MIT" and probe.layout_known and probe.matched
    assert probe.debits_count == 2 and probe.taxes == ("COFINS", "PIS")
    assert probe.has_taxpayer_id is False and probe.has_assessment_period is True
    assert str(path) not in serialized
    assert "11144477735" not in serialized
    assert "810902" not in serialized
    assert "principal" not in serialized


def test_parser_has_no_historical_adoption_date_rule(tmp_path: Path) -> None:
    payload = _payload("PisPasep", period={"MesApuracao": 1, "AnoApuracao": 2001})
    result = _run(_write(tmp_path / "historical.json", payload))

    assert result.extraction_status is ExtractionStatus.MATCHED
    assert _document(result).assessment_period.period == "2001-01"  # type: ignore[union-attr]
    assert all("HISTOR" not in warning and "ADOPTION" not in warning for warning in result.warnings)
