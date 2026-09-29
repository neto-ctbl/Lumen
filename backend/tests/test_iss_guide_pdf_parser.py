from __future__ import annotations

from decimal import Decimal
import hashlib
import json
from pathlib import Path

import fitz
import pytest

from agent.parsers.contracts import DocumentContext, DocumentSignal, ExtractionStatus, SignalProvenance, TechnicalFormat
from agent.parsers.iss_guide import (
    ANAPOLIS_DUAM_LAYOUT_ID,
    ISS_PARSER_NAME,
    NEROPOLIS_DUAM_LAYOUT_ID,
    AnapolisDuamExtractor,
    IssGuideFile,
    IssGuidePdfParser,
)
from agent.parsers.iss_guide_probe import sanitized_iss_summary
from agent.parsers.layout_framework import default_layout_registry
from agent.parsers.runtime import DocumentParserRuntime, default_parser_registry


def _columns(*items: tuple[int, str]) -> str:
    line = ""
    for position, value in items:
        line = line.ljust(position) + value
    return line


def _anapolis_lines(
    *,
    description: str = "Ref. a 8/2026 ISSQN Prest. Serv. Retido",
    principal: str = "100,00",
    correction: str = "2,00",
    interest: str = "1,00",
    penalty: str = "3,00",
    total: str = "106,00",
    document_number: str = "100000001",
    taxpayer: bool = True,
) -> list[str]:
    lines = [
        "Prefeitura Municipal de Anapolis                         Data Emissao 01/09/2026",
        "Diretoria da Receita-Gerencia de Fiscalizacao            Nr. da Guia 100000001",
        "Documento Unico de Arrecadacao Municipal - DUAM           Nosso Numero 900000001",
        f"Vencimento 15/09/2026                                    guia {document_number}",
        _columns((0, "Nome do Pagador"), (70, "Inscricao Municipal"), (105, "CPF/CNPJ")),
        _columns((0, "EMPRESA SINTETICA LTDA"), (70, "12345"), (105, "12.345.678/0001-95" if taxpayer else "-")),
        _columns((0, "Data de Vencimento"), (25, "No do Lancto."), (45, "Descricao"),
                 (105, "Valor Principal"), (125, "Correcao"), (145, "Juros"), (160, "Multa"), (175, "Total")),
        f"15/09/2026 700001 {description} {principal} {correction} {interest} {penalty} {total}",
    ]
    lines[1] = lines[1].replace("100000001", document_number)
    return lines


def _neropolis_lines(
    *,
    code: str = "002",
    description: str = "ISSQN PROPRIO",
    principal: str = "100,00",
    correction: str = "2,00",
    penalty: str = "3,00",
    interest: str = "1,00",
    discount: str = "0,00",
    total: str = "106,00",
) -> list[str]:
    return [
        "PREFEITURA MUNICIPAL DE NEROPOLIS                         DUAM 800000001",
        "Secretaria de Financas e Administracao",
        "Documento Unico de Arrecadacao Municipal                  ISSQN",
        "Contribuinte: EMPRESA SINTETICA LTDA",
        "CNPJ/CPF: 12.345.678/0001-95",
        "Inscricao Municipal: 54321",
        _columns((0, "REFERENCIA"), (25, "PARCELA"), (45, "EMISSAO"), (65, "CONVENIO"),
                 (85, "VENCIMENTO"), (105, "VALIDADE ATE")),
        _columns((0, "08/2026"), (25, "UNICA"), (45, "01/09/2026"), (65, "1"),
                 (85, "15/09/2026"), (105, "15/09/2026")),
        "TRIBUTO QUANTIDADE B. CALCULO ALIQUOTA VALOR ORIGINAL ATUALIZACAO MULTA JUROS DESCONTO TOTAL",
        f"{code} - {description} 100,00 100,00 2 % {principal} {correction} {penalty} {interest} {discount} {total}",
        "DESCRICAO",
        "(=) SALDO A RECOLHER R$ 106.00",
        "Nosso Numero 900000001",
    ]


def _write(tmp_path: Path, pages: list[list[str]], filename: str = "arquivo-neutro.pdf") -> Path:
    path = tmp_path / filename
    with fitz.open() as pdf:
        for lines in pages:
            page = pdf.new_page(width=1300, height=1500)
            for index, line in enumerate(lines):
                page.insert_text((25, 30 + index * 16), line, fontsize=7, fontname="cour")
        pdf.save(str(path))
    return path


def _context(path: Path) -> DocumentContext:
    return DocumentContext(file_path=path, technical_format=TechnicalFormat.PDF)


def _run(path: Path, *signals: DocumentSignal):
    return DocumentParserRuntime(default_parser_registry()).run_file(path, context_signals=signals)


def _documents(result):
    return IssGuideFile.model_validate(result.structured_data).documents


@pytest.mark.parametrize(
    "lines,layout,classification",
    (
        (_anapolis_lines(description="Ref. a 8/2026 ISSQN Prest. Serv. Proprio"), ANAPOLIS_DUAM_LAYOUT_ID, "ISS_OWN"),
        (_anapolis_lines(), ANAPOLIS_DUAM_LAYOUT_ID, "ISS_WITHHELD"),
        (_neropolis_lines(), NEROPOLIS_DUAM_LAYOUT_ID, "ISS_OWN"),
    ),
)
def test_known_layouts_classify_from_content_with_neutral_filename(tmp_path, lines, layout, classification):
    result = _run(_write(tmp_path, [lines]))
    assert result.parser_name == ISS_PARSER_NAME and result.parser_version == "1"
    assert result.document_family == "ISS_GUIDE" and result.extraction_status is ExtractionStatus.MATCHED
    document, = _documents(result)
    assert document.header.layout == layout
    assert document.classification.classification == classification
    assert document.classification.source == "CONTENT_DESCRIPTION"
    assert document.header.reference_period.month == "2026-08"
    assert document.header.reference_period_source.startswith("CONTENT_")
    assert document.header.taxpayer_id == "12345678000195"
    assert document.header.taxpayer_id_structure_valid is True
    assert document.header.municipal_registration
    assert document.header.due_date == "2026-09-15"
    assert document.header.total_amount == Decimal("106.00")
    assert document.validation.sum_matches_total is True
    assert result.structured_data["documents"][0]["header"]["total_amount"] == "106.00"


def test_filename_and_path_are_only_hints_and_content_period_prevails(tmp_path):
    path = _write(tmp_path, [_anapolis_lines()], "ISS PROPRIO 07-2025.pdf")
    hint = DocumentSignal(name="period_from_path", value="2025-07", provenance=SignalProvenance.PATH, confidence=0.1)
    result = _run(path, hint)
    document, = _documents(result)
    assert document.classification.classification == "ISS_WITHHELD"
    assert document.header.reference_period.month == "2026-08"
    assert hint in result.signals
    content = next(signal for signal in result.signals if signal.name == "period_from_content")
    assert content.provenance is SignalProvenance.CONTENT


def test_known_layout_unknown_modality_preserves_structure(tmp_path):
    result = _run(_write(tmp_path, [_anapolis_lines(description="Ref. a 8/2026 ISSQN Servico Municipal")]))
    document, = _documents(result)
    assert result.document_family == "ISS_GUIDE" and result.extraction_status is ExtractionStatus.MATCHED
    assert document.header.layout == ANAPOLIS_DUAM_LAYOUT_ID
    assert document.classification.classification == "UNKNOWN"
    assert document.classification.classification_known is False
    assert document.revenues and "ISS_MODALITY_INCONCLUSIVE" in result.warnings
    signals = {signal.name: signal.value for signal in result.signals}
    assert signals["layout_id"] == ANAPOLIS_DUAM_LAYOUT_ID
    assert signals["classification_id"] == "UNKNOWN"


def test_unknown_municipal_code_is_preserved_and_warned(tmp_path):
    result = _run(_write(tmp_path, [_neropolis_lines(code="999")]))
    document, = _documents(result)
    revenue, = document.revenues
    assert revenue.revenue_code == "999" and revenue.description == "ISSQN PROPRIO"
    assert document.classification.classification == "ISS_OWN"
    assert "ISS_MUNICIPAL_REVENUE_CODE_UNKNOWN" in result.warnings


@pytest.mark.parametrize(
    "principal,correction,penalty,interest,discount,total,matches",
    (
        ("0,00", "0,00", "0,00", "0,00", "0,00", "0,00", True),
        ("100,00", "2,00", "3,00", "1,00", "5,00", "101,00", True),
        ("100,00", "2,00", "3,00", "1,00", "0,00", "999,00", False),
    ),
)
def test_decimal_components_zero_discount_and_total_validation(
    tmp_path, principal, correction, penalty, interest, discount, total, matches,
):
    result = _run(_write(tmp_path, [_neropolis_lines(
        principal=principal, correction=correction, penalty=penalty,
        interest=interest, discount=discount, total=total,
    )]))
    document, = _documents(result)
    assert document.validation.sum_matches_total is matches
    assert all(isinstance(component.amount, Decimal) for component in document.revenues[0].components)
    assert ("ISS_COMPONENT_TOTAL_MISMATCH" in result.warnings) is (not matches)


def test_optional_absent_taxpayer_is_null_and_warned(tmp_path):
    result = _run(_write(tmp_path, [_anapolis_lines(taxpayer=False)]))
    document, = _documents(result)
    assert document.header.taxpayer_id is None
    assert document.header.taxpayer_id_structure_valid is None
    assert "ISS_TAXPAYER_ID_MISSING" in result.warnings


def test_two_independent_guides_on_two_pages_are_preserved(tmp_path):
    result = _run(_write(tmp_path, [
        _anapolis_lines(description="Ref. a 7/2026 ISSQN Prest. Serv. Proprio", document_number="100000001"),
        _anapolis_lines(description="Ref. a 8/2026 ISSQN Prest. Serv. Retido", document_number="100000002"),
    ]))
    first, second = _documents(result)
    assert first.page_numbers == (1,) and second.page_numbers == (2,)
    assert first.header.document_number != second.header.document_number
    assert {first.classification.classification, second.classification.classification} == {"ISS_OWN", "ISS_WITHHELD"}
    assert "ISS_MULTIPLE_MODALITIES" in result.warnings


def test_wrapped_anapolis_modality_is_part_of_description(tmp_path):
    lines = _anapolis_lines(description="Ref. a 7/2026 ISSQN Prest. Serv.")
    lines[1] = lines[1].replace("Receita-Gerencia", "Receita -Gerencia")
    lines[5] = lines[5].replace("12.345.678/0001-95", "12.345.678/0001 -95")
    lines.append("                                  Proprio")
    result = _run(_write(tmp_path, [lines]))
    document, = _documents(result)
    revenue, = document.revenues
    assert document.header.layout == ANAPOLIS_DUAM_LAYOUT_ID
    assert document.classification.classification == "ISS_OWN"
    assert revenue.description.endswith("Proprio")
    assert revenue.reference_period.month == "2026-07"
    assert document.header.taxpayer_id == "12345678000195"
    assert document.header.taxpayer_id_structure_valid is True


def test_updated_guide_preserves_each_revenue_period_and_due_date(tmp_path):
    lines = _anapolis_lines(
        description="Ref. a 2/2026 ISSQN Prest. Serv. Proprio",
        principal="100,00", correction="0,00", interest="2,00", penalty="3,00", total="105,00",
    )
    lines.extend((
        "15/06/2026 700002 Ref. a 5/2026 ISSQN Prest. Serv. Proprio 200,00 0,00 4,00 6,00 210,00",
        "15/07/2026 700003 Ref. a 6/2026 ISSQN Prest. Serv. Proprio 300,00 0,00 6,00 9,00 315,00",
    ))
    result = _run(_write(tmp_path, [lines], "ISSQN ATUALIZADO.pdf"))
    document, = _documents(result)
    assert document.classification.classification == "ISS_OWN"
    assert document.header.reference_period is None
    assert document.header.reference_label is None
    assert document.header.total_amount == Decimal("630.00")
    assert document.validation.sum_matches_total is True
    assert [row.reference_period.month for row in document.revenues] == ["2026-02", "2026-05", "2026-06"]
    assert [row.due_date for row in document.revenues] == ["2026-09-15", "2026-06-15", "2026-07-15"]
    assert "ISS_MULTIPLE_REFERENCE_PERIODS" in result.warnings
    period_signal = next(signal for signal in result.signals if signal.name == "period_from_content")
    assert len(period_signal.value) == 3


@pytest.mark.parametrize(
    "lines,warning",
    (
        (["NOTA FISCAL DE SERVICOS ELETRONICA", "ISS RETIDO", "ALIQUOTA 2%", "VALOR ISS 10,00"], "NO_SUPPORTED_PARSER"),
        (["ACOMPANHAMENTO DE SERVICOS", "NFS-e", "ISS", "COMPETENCIA 08/2026", "TOTAL 10,00"], "NO_SUPPORTED_PARSER"),
    ),
)
def test_nfse_and_municipal_reports_are_not_guides(tmp_path, lines, warning):
    result = _run(_write(tmp_path, [lines], "ISS 08-2026.pdf"))
    assert result.extraction_status is ExtractionStatus.UNSUPPORTED
    assert result.document_family == "UNKNOWN" and result.warnings == (warning,)


def test_known_layout_with_explicit_installment_is_unsupported(tmp_path):
    path = _write(tmp_path, [_anapolis_lines() + ["PARCELAMENTO MUNICIPAL - PARCELA 02 DE 12"]])
    parser = IssGuidePdfParser()
    assert parser.supports(_context(path)) is True
    result = parser.parse(_context(path))
    assert result.extraction_status is ExtractionStatus.UNSUPPORTED
    assert result.warnings == ("ISS_INSTALLMENT_OR_COLLECTION_EXCLUDED",)


def test_unknown_municipal_layout_is_distinct_from_unknown_classification(tmp_path):
    path = _write(tmp_path, [[
        "PREFEITURA MUNICIPAL DE CIDADE SINTETICA",
        "DOCUMENTO DE ARRECADACAO MUNICIPAL",
        "GUIA ISS 08/2026 TOTAL 10,00",
    ]], "ISS 08-2026.pdf")
    result = _run(path)
    assert result.extraction_status is ExtractionStatus.UNSUPPORTED
    assert result.document_family == "UNKNOWN"
    assert result.warnings == ("UNKNOWN_GUIDE_LAYOUT",)
    assert result.signals[-1].name == "layout_id" and result.signals[-1].value == "UNKNOWN"


def test_corrupt_and_textless_pdf_outcomes_are_safe(tmp_path):
    corrupt = tmp_path / "ISS.pdf"
    corrupt.write_bytes(b"%PDF-corrupt")
    blank = tmp_path / "ISS blank.pdf"
    with fitz.open() as pdf:
        pdf.new_page()
        pdf.save(str(blank))
    runtime = DocumentParserRuntime(default_parser_registry())
    assert runtime.run_file(corrupt).extraction_status is ExtractionStatus.INVALID
    assert runtime.run_file(blank).extraction_status is ExtractionStatus.INCONCLUSIVE


def test_extraction_exception_is_sanitized(monkeypatch, tmp_path):
    path = _write(tmp_path, [_anapolis_lines()])
    parser = IssGuidePdfParser()

    def explode(_context):
        raise RuntimeError("sensitive synthetic content")

    monkeypatch.setattr(AnapolisDuamExtractor, "extract", explode)
    result = parser.parse(_context(path))
    assert result.extraction_status is ExtractionStatus.ERROR
    assert result.warnings == ("LAYOUT_EXTRACTION_ERROR",)
    assert "sensitive" not in result.model_dump_json()


def test_probe_is_sanitized_and_file_is_unchanged(tmp_path):
    path = _write(tmp_path, [_neropolis_lines()], "razao-social-cnpj-valor.pdf")
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    summary = sanitized_iss_summary(path)
    serialized = json.dumps(summary)
    assert summary["family"] == "ISS_GUIDE" and summary["layout_known"] is True
    assert summary["documents_count"] == 1 and summary["components_count"] == 5
    assert summary["classifications"] == ["ISS_OWN"]
    assert str(path) not in serialized and "12345678000195" not in serialized and "106.00" not in serialized
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_layout_registry_contains_only_explicit_new_layouts_in_order(tmp_path):
    registry = default_layout_registry()
    assert registry.layout_ids[-2:] == (ANAPOLIS_DUAM_LAYOUT_ID, NEROPOLIS_DUAM_LAYOUT_ID)
    path = _write(tmp_path, [_neropolis_lines()])
    assert registry.identify(_context(path)).layout_id == NEROPOLIS_DUAM_LAYOUT_ID
