from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import json

import pytest
from sqlalchemy import func, select

from agent.parsers.contracts import (
    DocumentContext,
    DocumentSignal,
    ExtractionStatus,
    SignalProvenance,
    TechnicalFormat,
)
from agent.parsers.das_pdf import DAS_PARSER_NAME, DAS_PARSER_VERSION, DasDocument, DasPdfParser
from agent.parsers.das_probe import sanitized_das_summary
from agent.parsers.runtime import DocumentParserRuntime, default_parser_registry
from backend.app.models.fiscal_document_parser_run import FiscalDocumentParserRun
from backend.app.models.fiscal_evidence import FiscalEvidence
from backend.app.models.fiscal_obligation_status import FiscalObligationStatus
from backend.app.models.organization import Organization
from backend.app.schemas.watcher import WatcherParserRunRequest
from backend.app.services.document_parser_runs import register_document_parser_run
from backend.tests.watcher_agent_test_utils import write_synthetic_text_pdf


def _das_lines(
    *,
    total: str = "606,00",
    due_date: str = "20/07/2026",
    pay_until: str = "20/07/2026",
    observation: str | None = None,
) -> list[str]:
    lines = [
        "Documento de Arrecadacao do Simples Nacional",
        "CNPJ: 12.345.678/0001-95",
        "Razao Social: EMPRESA SINTETICA LTDA",
        "Periodo de Apuracao: Junho/2026",
        f"Data de Vencimento: {due_date}",
        "Numero do Documento: 07.16.26111.0000001-0",
        f"Pagar este documento ate: {pay_until}",
        f"Valor Total do Documento: {total}",
        "Observacoes:",
    ]
    if observation is not None:
        lines.append(observation)
    lines.extend(
        [
        "Composicao do Documento de Arrecadacao",
        "Codigo Denominacao Principal Multa Juros Total",
        "1001 IRPJ - SIMPLES NACIONAL 100,00 5,00 1,00 106,00",
        "06/2026",
        "1007 ICMS - SIMPLES NACIONAL 200,00 200,00",
        "GO - 06/2026",
        "1010 ISS - SIMPLES NACIONAL 300,00 300,00",
        "CIDADE SINTETICA (GO) - 06/2026",
        "9099 CONTRIBUICAO SINTETICA DESCONHECIDA 0,00 0,00 0,00 0,00",
        "06/2026",
        f"Totais {total} {total}",
        ]
    )
    return lines


def _write_das(tmp_path: Path, *, name: str = "arquivo-neutro.pdf", **kwargs: str) -> Path:
    path = tmp_path / name
    write_synthetic_text_pdf(path, _das_lines(**kwargs))
    return path


def _document(path: Path) -> DocumentContext:
    return DocumentContext(file_path=path, technical_format=TechnicalFormat.PDF)


def _structured_document(result) -> dict[str, object]:
    document = result.structured_data["document"]
    assert isinstance(document, dict)
    return document


def test_complete_das_with_neutral_filename_is_content_matched_and_normalized(tmp_path: Path) -> None:
    result = DocumentParserRuntime(default_parser_registry()).run_file(_write_das(tmp_path))

    assert result.parser_name == DAS_PARSER_NAME
    assert result.parser_version == DAS_PARSER_VERSION
    assert result.document_family == "DAS"
    assert result.extraction_status is ExtractionStatus.MATCHED
    assert result.confidence == 1.0
    assert result.warnings == ()

    document = _structured_document(result)
    header = document["header"]
    assert header == {
        "cnpj": "12345678000195",
        "cnpj_structure_valid": True,
        "corporate_name": "EMPRESA SINTETICA LTDA",
        "assessment_period": "2026-06",
        "due_date": "2026-07-20",
        "document_number": "07.16.26111.0000001-0",
        "pay_until": "2026-07-20",
        "total_amount": "606.00",
    }
    validation = document["validation"]
    assert validation == {
        "components_total_amount": "606.00",
        "sum_matches_total": True,
        "pay_until_matches_due_date": True,
    }
    provenances = {signal.provenance for signal in result.signals}
    assert SignalProvenance.CONTENT in provenances
    assert SignalProvenance.FILE_STRUCTURE in provenances


def test_components_preserve_unknown_codes_regions_and_decimal_columns(tmp_path: Path) -> None:
    result = DocumentParserRuntime(default_parser_registry()).run_file(_write_das(tmp_path))
    components = _structured_document(result)["components"]
    assert isinstance(components, list)
    assert len(components) == 4

    assert components[0] == {
        "code": "1001",
        "denomination": "IRPJ - SIMPLES NACIONAL",
        "tax_family": "IRPJ",
        "assessment_period": "2026-06",
        "state": None,
        "municipality": None,
        "principal_amount": "100.00",
        "penalty_amount": "5.00",
        "interest_amount": "1.00",
        "total_amount": "106.00",
    }
    assert components[1]["tax_family"] == "ICMS"
    assert components[1]["state"] == "GO"
    assert components[1]["penalty_amount"] == "0.00"
    assert components[1]["interest_amount"] == "0.00"
    assert components[2]["tax_family"] == "ISS"
    assert components[2]["municipality"] == "CIDADE SINTETICA"
    assert components[2]["state"] == "GO"
    assert components[3]["code"] == "9099"
    assert components[3]["denomination"] == "CONTRIBUICAO SINTETICA DESCONHECIDA"
    assert components[3]["tax_family"] is None
    assert components[3]["total_amount"] == "0.00"


def test_filename_das_never_overrides_non_das_content(tmp_path: Path) -> None:
    path = tmp_path / "DAS-06-2026.pdf"
    write_synthetic_text_pdf(
        path,
        [
            "Documento de Arrecadacao de Receitas Federais",
            "DARF SENDA",
            "Periodo de Apuracao: 06/2026",
            "Valor Total: 100,00",
        ],
    )
    parser = DasPdfParser()

    assert parser.supports(_document(path)) is False
    result = DocumentParserRuntime(default_parser_registry()).run_file(path)
    assert result.extraction_status is ExtractionStatus.UNSUPPORTED
    assert result.document_family == "UNKNOWN"


def test_das_with_only_ic_observation_remains_supported(tmp_path: Path) -> None:
    result = DocumentParserRuntime(default_parser_registry()).run_file(
        _write_das(tmp_path, observation="IC")
    )

    assert result.extraction_status is ExtractionStatus.MATCHED
    assert result.document_family == "DAS"


@pytest.mark.parametrize(
    "observation",
    (
        "PGFN-SISPAR: IDENTIFICADOR SINTETICO",
        "PARC-SN: IDENTIFICADOR SINTETICO",
        "PERT: IDENTIFICADOR SINTETICO",
        "RELP: IDENTIFICADOR SINTETICO",
    ),
)
def test_installment_using_das_shell_is_rejected_by_observation(
    tmp_path: Path, observation: str
) -> None:
    path = tmp_path / "arquivo-neutro.pdf"
    write_synthetic_text_pdf(path, _das_lines(observation=observation))

    parser = DasPdfParser()
    assert parser.supports(_document(path)) is False

    result = DocumentParserRuntime(default_parser_registry()).run_file(path)
    if observation.startswith("PARC-SN"):
        assert result.extraction_status is ExtractionStatus.UNSUPPORTED
        assert result.document_family == "UNKNOWN"
    else:
        assert result.extraction_status is ExtractionStatus.MATCHED
        assert result.document_family == "INSTALLMENT"


def test_debt_active_components_are_a_secondary_installment_exclusion(tmp_path: Path) -> None:
    path = tmp_path / "arquivo-neutro.pdf"
    lines = _das_lines()
    lines[11] = "1469 REC.DIVIDA ATIVA-IRPJ-SIMPLES NACIONAL 100,00 5,00 1,00 106,00"
    write_synthetic_text_pdf(path, lines)

    parser = DasPdfParser()
    assert parser.supports(_document(path)) is False

    result = DocumentParserRuntime(default_parser_registry()).run_file(path)
    assert result.extraction_status is ExtractionStatus.UNSUPPORTED
    assert result.document_family == "UNKNOWN"


def test_incomplete_but_conclusive_das_has_lower_confidence_and_warnings(tmp_path: Path) -> None:
    path = tmp_path / "incompleto.pdf"
    write_synthetic_text_pdf(
        path,
        [
            "Documento de Arrecadacao do Simples Nacional",
            "Periodo de Apuracao: Junho/2026",
            "Valor Total do Documento: 10,00",
            "Composicao do Documento de Arrecadacao",
        ],
    )

    result = DocumentParserRuntime(default_parser_registry()).run_file(path)

    assert result.extraction_status is ExtractionStatus.MATCHED
    assert result.confidence is not None and result.confidence < 1.0
    assert "DAS_CNPJ_MISSING" in result.warnings
    assert "DAS_COMPONENTS_MISSING" in result.warnings


def test_total_mismatch_warns_without_rejecting_document(tmp_path: Path) -> None:
    result = DocumentParserRuntime(default_parser_registry()).run_file(
        _write_das(tmp_path, total="607,00")
    )

    assert result.extraction_status is ExtractionStatus.MATCHED
    assert "DAS_COMPONENT_TOTAL_MISMATCH" in result.warnings
    assert _structured_document(result)["validation"]["sum_matches_total"] is False


def test_due_date_and_pay_until_are_preserved_when_different(tmp_path: Path) -> None:
    result = DocumentParserRuntime(default_parser_registry()).run_file(
        _write_das(tmp_path, pay_until="21/07/2026")
    )
    header = _structured_document(result)["header"]

    assert header["due_date"] == "2026-07-20"
    assert header["pay_until"] == "2026-07-21"
    assert "DAS_PAY_UNTIL_DIFFERS_FROM_DUE_DATE" in result.warnings


def test_content_period_wins_without_erasing_path_period_signal(tmp_path: Path) -> None:
    path_signal = DocumentSignal(
        name="period_from_path",
        value="2026-07",
        provenance=SignalProvenance.PATH,
        confidence=0.2,
    )
    result = DocumentParserRuntime(default_parser_registry()).run_file(
        _write_das(tmp_path), context_signals=(path_signal,)
    )

    assert _structured_document(result)["header"]["assessment_period"] == "2026-06"
    signal_values = {(signal.name, signal.value, signal.provenance) for signal in result.signals}
    assert ("period_from_path", "2026-07", SignalProvenance.PATH) in signal_values
    assert ("period_from_content", "2026-06", SignalProvenance.CONTENT) in signal_values


def test_blank_pdf_is_inconclusive_and_corrupt_pdf_is_invalid(tmp_path: Path) -> None:
    blank = tmp_path / "blank.pdf"
    write_synthetic_text_pdf(blank, [])
    corrupt = tmp_path / "corrupt.pdf"
    corrupt.write_bytes(b"%PDF-1.4\nsynthetic-corruption")
    runtime = DocumentParserRuntime(default_parser_registry())

    blank_result = runtime.run_file(blank)
    corrupt_result = runtime.run_file(corrupt)

    assert blank_result.extraction_status is ExtractionStatus.INCONCLUSIVE
    assert blank_result.warnings == ("PDF_TEXT_LAYER_MISSING",)
    assert corrupt_result.extraction_status is ExtractionStatus.INVALID
    assert corrupt_result.warnings == ("INVALID_PDF",)


def test_sanitized_probe_returns_only_presence_and_validation_metadata(tmp_path: Path) -> None:
    summary = sanitized_das_summary(_write_das(tmp_path, name="DAS EMPRESA SINTETICA.pdf"))
    serialized = json.dumps(summary, sort_keys=True)

    assert summary == {
        "family": "DAS",
        "matched": True,
        "extraction_status": "MATCHED",
        "components_count": 4,
        "has_cnpj": True,
        "has_assessment_period": True,
        "has_due_date": True,
        "has_document_number": True,
        "has_total": True,
        "sum_matches_total": True,
        "warning_codes": [],
    }
    assert "12345678000195" not in serialized
    assert "EMPRESA SINTETICA" not in serialized
    assert "606.00" not in serialized
    assert str(tmp_path) not in serialized


def test_das_parser_run_replay_is_idempotent_and_does_not_mutate_evidence(
    tmp_path: Path, db_session
) -> None:
    organization = Organization(name="Synthetic DAS Parser", slug="synthetic-das-parser")
    db_session.add(organization)
    db_session.flush()
    evidence = FiscalEvidence(
        organization_id=organization.id,
        source="WATCHER_FILE",
        source_type="WATCHER_INGEST",
        file_hash=f"{organization.id:064x}"[-64:],
        status="PENDENTE",
    )
    db_session.add(evidence)
    db_session.flush()
    before_obligations = db_session.scalar(select(func.count()).select_from(FiscalObligationStatus))
    result = DocumentParserRuntime(default_parser_registry()).run_file(_write_das(tmp_path))
    payload = WatcherParserRunRequest.model_validate(result.to_backend_payload())

    first = register_document_parser_run(
        db_session, organization=organization, evidence_id=evidence.id, payload=payload
    )
    replay = register_document_parser_run(
        db_session, organization=organization, evidence_id=evidence.id, payload=payload
    )

    assert first.created is True and replay.created is False
    assert first.parser_run.id == replay.parser_run.id
    assert db_session.scalar(select(func.count()).select_from(FiscalDocumentParserRun)) == 1
    assert db_session.scalar(select(func.count()).select_from(FiscalObligationStatus)) == before_obligations
    db_session.refresh(evidence)
    assert evidence.detected_tax is None
    assert evidence.detected_obligation is None
    assert evidence.cnpj_detected is None
    assert evidence.competencia_detected is None
    assert evidence.confidence is None


def test_internal_money_values_are_decimal_not_float(tmp_path: Path) -> None:
    parser = DasPdfParser()
    extraction = parser.parse(_document(_write_das(tmp_path)))
    document = extraction.structured_data["document"]
    assert isinstance(document, dict)
    typed_document = DasDocument.model_validate(document)
    assert isinstance(typed_document.header.total_amount, Decimal)
    assert document["header"]["total_amount"] == "606.00"
    assert Decimal(document["header"]["total_amount"]) == Decimal("606.00")
