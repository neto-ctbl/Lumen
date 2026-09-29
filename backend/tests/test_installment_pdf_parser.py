from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import json

import fitz
import pytest

from agent.parsers.contracts import DocumentContext, ExtractionStatus, TechnicalFormat
from agent.parsers.darf_pdf import DarfPdfParser
from agent.parsers.das_pdf import DasPdfParser
from agent.parsers.installment_pdf import (
    INSTALLMENT_PARSER_NAME,
    INSTALLMENT_PARSER_VERSION,
    InstallmentFile,
    InstallmentPdfParser,
)
from agent.parsers.installment_probe import sanitized_installment_summary
from agent.parsers.legacy_darf import LEGACY_DARF_FORM_LAYOUT_ID
from agent.parsers.runtime import DocumentParserRuntime, default_parser_registry
from agent.parsers.state_guide_pdf import StateGuidePdfParser
from backend.tests.test_darf_pdf_parser import _lines as darf_lines
from backend.tests.test_darf_pdf_parser import _write as write_darf
from backend.tests.test_das_pdf_parser import _write_das as write_das
from backend.tests.test_state_guide_pdf_parser import _lines as state_lines
from backend.tests.test_state_guide_pdf_parser import _write as write_state
from backend.tests.watcher_agent_test_utils import write_synthetic_text_pdf


def _run(path: Path):
    return DocumentParserRuntime(default_parser_registry()).run_file(path)


def _documents(path: Path):
    result = _run(path)
    return result, InstallmentFile.model_validate(result.structured_data).documents


@pytest.mark.parametrize(
    "observation,program,administrator,scope",
    (
        ("DAS de PARCSN Numero do Parcelamento: 7 Parcela: 9/22", "PARCSN", "SIMPLES_NACIONAL", "SIMPLES_NACIONAL"),
        ("DAS de PARCMEI Numero do Parcelamento: 8 Numero da Parcela: 31/56", "PARCMEI", "SIMPLES_NACIONAL", "SIMEI"),
        ("DAS de SIMEI Numero do Parcelamento: 8 Numero da Parcela: 31/56", "PARCMEI", "SIMPLES_NACIONAL", "SIMEI"),
        ("DAS do Parcelamento RELPSN Numero do Parcelamento: 9 Parcela: 50/113", "RELP", "SIMPLES_NACIONAL", "SIMPLES_NACIONAL"),
        ("DAS do Parcelamento PERTSN Numero do Parcelamento: 10 Parcela: 96/126", "PERT", "SIMPLES_NACIONAL", "SIMPLES_NACIONAL"),
    ),
)
def test_das_form_programs_use_content_not_filename(
    tmp_path: Path,
    observation: str,
    program: str,
    administrator: str,
    scope: str,
) -> None:
    path = write_das(tmp_path, name="nome-neutro.pdf", observation=observation)
    result, documents = _documents(path)
    document, = documents

    assert result.parser_name == INSTALLMENT_PARSER_NAME
    assert result.parser_version == INSTALLMENT_PARSER_VERSION
    assert result.document_family == "INSTALLMENT"
    assert result.extraction_status is ExtractionStatus.MATCHED
    assert document.program == program and document.administrator == administrator
    assert document.debt.scope == scope
    assert document.header.layout == "DAS_FORM"
    assert document.installment.current_installment is not None
    assert document.installment.total_installments is not None
    assert document.installment.agreement_number is not None
    assert document.debt.original_debt_periods
    assert any(component.penalty_amount == Decimal("0.00") for component in document.components)
    assert document.validation.sum_matches_total is True
    assert DasPdfParser().supports(DocumentContext(file_path=path, technical_format=TechnicalFormat.PDF)) is False


def test_pgfn_uses_federal_layout_and_does_not_infer_tax_from_filename(tmp_path: Path) -> None:
    path = write_darf(tmp_path, lines=darf_lines(code="4162", tax="DIVIDA ATIVA", observation="PGFN-SISPAR: 123456789"))
    result, documents = _documents(path)
    document, = documents

    assert document.program == "PGFN" and document.administrator == "PGFN"
    assert document.debt.scope == "FEDERAL" and document.debt.taxes == ()
    assert document.debt.raw_debt_description == "DIVIDA_ATIVA"
    assert document.installment.agreement_number == "123456789"
    assert document.components[0].code == "4162"
    assert "INSTALLMENT_TAXES_UNKNOWN" in result.warnings
    assert DarfPdfParser().supports(DocumentContext(file_path=path, technical_format=TechnicalFormat.PDF)) is False


def test_pgfn_das_like_uses_same_program_without_changing_layout_identity(tmp_path: Path) -> None:
    path = write_das(
        tmp_path,
        name="arquivo-neutro.pdf",
        observation="PGFN-SISPAR: 123456789 Parcela: 14/18",
    )
    result, documents = _documents(path)
    document, = documents
    assert result.extraction_status is ExtractionStatus.MATCHED
    assert document.header.layout == "DAS_FORM"
    assert document.program == "PGFN" and document.administrator == "PGFN"
    assert document.debt.scope == "FEDERAL"
    assert document.installment.current_installment == 14
    assert document.installment.total_installments == 18


def test_sefaz_installment_reuses_dare_and_preserves_all_coded_components(tmp_path: Path) -> None:
    lines = state_lines(installment="03", total="108,00")
    document_index = next(index for index, line in enumerate(lines) if "Documento de Origem" in line)
    lines.insert(document_index, " ".ljust(100) + "Correcao Monetaria (900004) 2,00")
    lines[-1] = "Informacoes complementares: PARCELAMENTO NR: 123456 ----- 003 / 018"
    path = write_state(tmp_path, pages=[lines], filename="nome-neutro.pdf")
    result, documents = _documents(path)
    document, = documents

    assert document.program == "SEFAZ" and document.administrator == "SEFAZ_GO"
    assert document.debt.scope == "STATE" and document.debt.taxes == ("ICMS",)
    assert document.header.layout == "DARE_GO_5_1"
    assert document.installment.current_installment == 3
    assert document.installment.total_installments == 18
    assert document.validation.sum_matches_total is True
    assert len(document.components) == 4
    assert sum(
        (component.correction_amount or Decimal("0.00") for component in document.components),
        Decimal("0.00"),
    ) == Decimal("2.00")
    assert StateGuidePdfParser().supports(DocumentContext(file_path=path, technical_format=TechnicalFormat.PDF)) is False


def _legacy_lines(*, code: str = "1124", total: str = "106,00") -> list[str]:
    return [
        "MINISTERIO DA FAZENDA DARF",
        "DOCUMENTO DE ARRECADACAO DE RECEITAS FEDERAIS",
        "01 NOME / RAZAO SOCIAL: EMPRESA SINTETICA LTDA",
        "02 PERIODO DE APURACAO: 30/06/2026",
        "03 NUMERO DO CPF OU CNPJ: 12.345.678/0001-95",
        f"04 CODIGO DA RECEITA: {code}",
        "05 NUMERO DE REFERENCIA:",
        "06 DATA DE VENCIMENTO: 31/07/2026",
        "07 VALOR DO PRINCIPAL: 100,00",
        "08 VALOR DA MULTA: 5,00",
        "09 VALOR DOS JUROS E / OU ENCARGOS DL - 1.025/69: 1,00",
        f"10 VALOR TOTAL: {total}",
        "DATA LIMITE PARA ACOLHIMENTO: 31/07/2026",
        "OBSERVACAO:",
        "0211000120000000000000000",
        "18",
        "11 AUTENTICACAO BANCARIA",
    ]


def _write_legacy(tmp_path: Path, *, code: str = "1124", copies: int = 1, filename: str = "neutro.pdf") -> Path:
    path = tmp_path / filename
    write_synthetic_text_pdf(path, _legacy_lines(code=code) * copies)
    return path


def test_simplified_installment_creates_only_structural_legacy_layout(tmp_path: Path) -> None:
    path = _write_legacy(tmp_path)
    result, documents = _documents(path)
    document, = documents

    assert document.program == "SIMPLIFICADO" and document.administrator == "RFB"
    assert document.debt.scope == "FEDERAL" and document.debt.taxes == ()
    assert document.header.layout == LEGACY_DARF_FORM_LAYOUT_ID
    assert document.installment.agreement_number == "0211000120000000000000000"
    assert document.installment.current_installment == 18
    assert document.installment.total_installments is None
    assert document.debt.original_debt_periods == ()
    assert document.payment.principal_amount == Decimal("100.00")
    assert document.payment.penalty_amount == Decimal("5.00")
    assert document.payment.interest_amount == Decimal("1.00")
    assert document.payment.total_amount == Decimal("106.00")
    assert document.validation.sum_matches_total is True


def test_repeated_legacy_payment_copy_is_deduplicated_by_document_identity(tmp_path: Path) -> None:
    result, documents = _documents(_write_legacy(tmp_path, copies=2))
    assert result.extraction_status is ExtractionStatus.MATCHED
    assert len(documents) == 1


def test_unknown_installment_program_and_revenue_code_are_preserved(tmp_path: Path) -> None:
    path = _write_legacy(tmp_path, code="9999")
    # Revenue 9999 alone is not authoritative for an installment.
    assert _run(path).extraction_status is ExtractionStatus.UNSUPPORTED

    das = write_das(
        tmp_path,
        name="programa-desconhecido.pdf",
        observation="Parcelamento Numero do Parcelamento: 123 Parcela: 2/10",
    )
    result, documents = _documents(das)
    assert documents[0].program == "UNKNOWN"
    assert result.extraction_status is ExtractionStatus.MATCHED
    assert "INSTALLMENT_PROGRAM_UNKNOWN" in result.warnings


def test_filename_does_not_create_or_override_installment_classification(tmp_path: Path) -> None:
    normal = write_das(tmp_path, name="PGFN PARCSN PERT RELP PARCELAMENTO.pdf")
    result = _run(normal)
    assert result.document_family == "DAS" and result.extraction_status is ExtractionStatus.MATCHED

    pert = write_das(
        tmp_path,
        name="PARCSN.pdf",
        observation="DAS do Parcelamento PERTSN Numero do Parcelamento: 10 Parcela: 2/10",
    )
    assert _documents(pert)[1][0].program == "PERT"


def test_multiple_documents_preserve_order_and_distinct_programs(tmp_path: Path) -> None:
    path = tmp_path / "bundle.pdf"
    with fitz.open() as pdf:
        for observation in (
            "DAS de PARCSN Numero do Parcelamento: 7 Parcela: 9/22",
            "DAS do Parcelamento RELPSN Numero do Parcelamento: 9 Parcela: 50/113",
        ):
            page = pdf.new_page(width=1000, height=1300)
            from backend.tests.test_das_pdf_parser import _das_lines

            for index, line in enumerate(_das_lines(observation=observation)):
                page.insert_text((25, 30 + index * 15), line, fontsize=7, fontname="cour")
        pdf.save(str(path))

    result, documents = _documents(path)
    assert [document.program for document in documents] == ["PARCSN", "RELP"]
    assert result.confidence == 1
    assert next(signal.value for signal in result.signals if signal.name == "classification_id") == "MULTIPLE"


def test_invalid_and_textless_pdf_have_sanitized_nonmatched_outcomes(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.pdf"
    invalid.write_bytes(b"not a pdf")
    textless = tmp_path / "textless.pdf"
    write_synthetic_text_pdf(textless, [])

    parser = InstallmentPdfParser()
    invalid_result = parser.parse(DocumentContext(file_path=invalid, technical_format=TechnicalFormat.PDF))
    textless_result = parser.parse(DocumentContext(file_path=textless, technical_format=TechnicalFormat.PDF))
    assert invalid_result.extraction_status is ExtractionStatus.INVALID
    assert textless_result.extraction_status is ExtractionStatus.INCONCLUSIVE
    assert "INVALID_PDF" in invalid_result.warnings
    assert "PDF_TEXT_LAYER_MISSING" in textless_result.warnings


def test_unknown_layout_with_installment_words_is_not_guessed(tmp_path: Path) -> None:
    path = tmp_path / "PARCELAMENTO PGFN.pdf"
    write_synthetic_text_pdf(path, ["PARCELAMENTO", "PGFN", "FORMULARIO FISCAL DESCONHECIDO"])
    result = _run(path)
    assert result.extraction_status is ExtractionStatus.UNSUPPORTED
    assert result.document_family == "UNKNOWN"
    assert result.structured_data == {}


def test_sanitized_probe_exposes_only_allowlisted_aggregates(tmp_path: Path) -> None:
    path = write_das(
        tmp_path,
        name="empresa-sintetica-parcelamento.pdf",
        observation="DAS de PARCSN Numero do Parcelamento: 7 Parcela: 9/22",
    )
    summary = sanitized_installment_summary(path)
    serialized = json.dumps(summary, sort_keys=True)
    assert summary == {
        "family": "INSTALLMENT",
        "matched": True,
        "extraction_status": "MATCHED",
        "documents_count": 1,
        "programs": ["PARCSN"],
        "layouts": ["DAS_FORM"],
        "administrators": ["SIMPLES_NACIONAL"],
        "debt_scopes": ["SIMPLES_NACIONAL"],
        "identified_tax_count": 3,
        "components_count": 4,
        "has_taxpayer_id": True,
        "has_installment_reference": True,
        "has_current_installment": True,
        "has_total_installments": True,
        "has_reference_period": True,
        "has_due_date": True,
        "has_total": True,
        "sum_matches_total": True,
        "warning_codes": [],
    }
    assert "12345678000195" not in serialized
    assert "EMPRESA SINTETICA" not in serialized
    assert "606.00" not in serialized
    assert str(path) not in serialized


def test_legacy_total_mismatch_is_visible_without_changing_classification(tmp_path: Path) -> None:
    path = tmp_path / "legacy-mismatch.pdf"
    write_synthetic_text_pdf(path, _legacy_lines(total="107,00"))
    result, documents = _documents(path)
    assert documents[0].program == "SIMPLIFICADO"
    assert documents[0].validation.sum_matches_total is False
    assert "REVENUE_TOTAL_MISMATCH" in result.warnings
