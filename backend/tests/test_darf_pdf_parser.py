from __future__ import annotations

from decimal import Decimal
import hashlib
import json

import fitz
import pytest
from sqlalchemy import func, select

from agent.parsers.contracts import DocumentContext, DocumentSignal, ExtractionStatus, SignalProvenance, TechnicalFormat
from agent.parsers.darf_pdf import DARF_PARSER_NAME, DarfFile, DarfPdfParser
from agent.parsers.darf_probe import sanitized_darf_summary
from agent.parsers.darf_tax_codes import REVENUE_TAX_CODES, identify_tax
from agent.parsers.das_pdf import DasPdfParser
from agent.parsers.federal_revenue_guide import FederalRevenueGuideExtractor, PeriodKind, parse_guide_period
from agent.parsers.runtime import DocumentParserRuntime, ParserRegistry, default_parser_registry
from backend.app.models.fiscal_document_parser_run import FiscalDocumentParserRun
from backend.app.models.fiscal_evidence import FiscalEvidence
from backend.app.models.fiscal_obligation_status import FiscalObligationStatus
from backend.app.models.organization import Organization
from backend.app.schemas.watcher import WatcherParserRunRequest
from backend.app.services.document_parser_runs import register_document_parser_run
from backend.tests.watcher_agent_test_utils import write_synthetic_text_pdf


def _lines(*, code="8109", tax="PIS", period="06/2026", header_period=None,
           number="07.16.26111.0000001-0", total="1.240,56", observation="IC", values="1.234,56 5,00 1,00 1.240,56"):
    return [
        "Documento de Arrecadacao", "de Receitas Federais",
        "CNPJ: 12.345.678/0001-95", "Razao Social: EMPRESA SINTETICA LTDA",
        f"Periodo de Apuracao: {header_period or period}", "Data de Vencimento: 24/07/2026",
        f"Numero do Documento: {number}", "Pagar este documento ate: 24/07/2026",
        f"Valor Total do Documento: {total}", "Observacoes:", observation,
        "Composicao do Documento de Arrecadacao",
        "Codigo Denominacao Principal Multa Juros Total",
        f"{code} {tax} - CONTRIBUICAO SINTETICA {values}", f"01 {tax} - DETALHE SINTETICO",
        f"PA:{period} Vencimento:24/07/2026", f"Totais {total} {total}", "SENDA (Versao:1.0.0) Pagina:1/1",
        # Payment slip repeats the title/identifier but is not a second guide.
        "Documento de Arrecadacao de Receitas Federais",
        "85870000000 1 11111111111 1 22222222222 2 33333333333 3",
        "CNPJ: 12.345.678/0001-95", f"Numero: {number}",
    ]


def _write(tmp_path, lines=None, **kwargs):
    path = tmp_path / "arquivo-neutro.pdf"
    write_synthetic_text_pdf(path, lines if lines is not None else _lines(**kwargs))
    return path


def _write_pages(tmp_path, pages):
    path = tmp_path / "bundle.pdf"
    with fitz.open() as pdf:
        for lines in pages:
            page = pdf.new_page()
            for i, line in enumerate(lines):
                page.insert_text((30, 35 + i * 18), line, fontsize=8)
        pdf.save(str(path))
    return path


def _context(path):
    return DocumentContext(file_path=path, technical_format=TechnicalFormat.PDF)


def _run(path):
    return DocumentParserRuntime(default_parser_registry()).run_file(path)


def _docs(result):
    return DarfFile.model_validate(result.structured_data).documents


@pytest.mark.parametrize("code,tax", REVENUE_TAX_CODES.items())
def test_validated_code_mapping_neutral_filename_decimal_header_and_revenues(tmp_path, code, tax):
    result = _run(_write(tmp_path, code=code, tax=tax))
    assert result.parser_name == DARF_PARSER_NAME and result.parser_version == "1"
    assert result.document_family == "DARF" and result.extraction_status is ExtractionStatus.MATCHED
    assert result.confidence == 1 and result.warnings == ()
    doc, = _docs(result)
    assert doc.header.taxpayer_id == "12345678000195"
    assert doc.header.taxpayer_id_structure_valid is True
    assert doc.header.taxpayer_name == "EMPRESA SINTETICA LTDA"
    assert doc.header.assessment_period.month == "2026-06"
    assert doc.header.due_date == doc.header.pay_until == "2026-07-24"
    assert doc.header.document_number == "07.16.26111.0000001-0"
    assert doc.header.total_amount == Decimal("1240.56")
    row, = doc.revenues
    assert row.revenue_code == code and row.code_extension == "01" and row.tax == tax
    assert row.tax_identification_source == "REVENUE_CODE"
    assert row.principal_amount == Decimal("1234.56")
    assert row.penalty_amount == Decimal("5.00") and row.interest_amount == Decimal("1.00")
    assert row.total_amount == Decimal("1240.56")
    assert doc.validation.sum_matches_total is True
    assert result.structured_data["documents"][0]["header"]["total_amount"] == "1240.56"
    assert DasPdfParser().supports(_context(_write(tmp_path, code=code, tax=tax))) is False


@pytest.mark.parametrize("period", ("2o Trimestre/2026", "2 Trimestre 2026", "2. Trimestre/2026"))
@pytest.mark.parametrize("code,tax", (("2089", "IRPJ"), ("2372", "CSLL")))
def test_explicit_quarter_over_monthly_header_preserves_both_and_never_uses_path(tmp_path, period, code, tax):
    path = _write(tmp_path, period=period, header_period="Junho/2026", code=code, tax=tax)
    hint = DocumentSignal(name="period_from_path", value="2026-08", provenance=SignalProvenance.PATH, confidence=0.1)
    result = DocumentParserRuntime(default_parser_registry()).run_file(path, context_signals=(hint,))
    doc, = _docs(result)
    pa = doc.header.assessment_period
    assert pa.kind is PeriodKind.QUARTER and pa.quarter == 2 and pa.year == 2026
    assert pa.month is None and pa.period_start is None and pa.period_end is None
    assert doc.header.observed_header_period.month == "2026-06"
    assert doc.header.assessment_period_source == "REVENUES_CONSENSUS"
    assert "DARF_ASSESSMENT_PERIOD_HEADER_DIFFERS_FROM_REVENUES" in result.warnings
    assert hint in result.signals
    content = next(s for s in result.signals if s.name == "period_from_content")
    assert content.provenance is SignalProvenance.CONTENT and content.value[0]["period"]["month"] is None


@pytest.mark.parametrize("label,kind", (("Junho/2026", PeriodKind.MONTH), ("30/06/2026", PeriodKind.DATE),
                                      ("01/04/2026 a 30/06/2026", PeriodKind.RANGE),
                                      ("Periodo Especial", PeriodKind.UNKNOWN), ("31/02/2026", PeriodKind.UNKNOWN)))
def test_period_semantics_do_not_force_dates_or_unknown_labels_to_month(label, kind):
    period = parse_guide_period(label)
    assert period.kind is kind and period.label == label
    if kind is not PeriodKind.MONTH:
        assert period.month is None


def test_one_unified_darf_has_multiple_revenues_not_multiple_documents(tmp_path):
    lines = _lines(total="1.240,56")
    start = lines.index("Totais 1.240,56 1.240,56")
    lines[start:start] = ["2172 COFINS - SINTETICO 0,00 0,00 0,00 0,00", "PA:06/2026 Vencimento:24/07/2026"]
    doc, = _docs(_run(_write(tmp_path, lines)))
    assert len(doc.revenues) == 2 and {r.tax for r in doc.revenues} == {"PIS", "COFINS"}
    assert doc.validation.sum_matches_total is True


def test_two_independent_darfs_in_pdf_keep_headers_totals_and_source_pages_separate(tmp_path):
    path = _write_pages(tmp_path, [_lines(code="2484", tax="CSLL"),
                                  _lines(code="5993", tax="IRPJ", number="07.16.26111.0000002-0", total="0,00", values="0,00 0,00")])
    docs = _docs(_run(path))
    assert len(docs) == 2 and [d.page_numbers for d in docs] == [(1,), (2,)]
    assert docs[0].header.document_number != docs[1].header.document_number
    assert [d.header.total_amount for d in docs] == [Decimal("1240.56"), Decimal("0.00")]
    assert [d.revenues[0].tax for d in docs] == ["CSLL", "IRPJ"]
    assert all(d.validation.sum_matches_total for d in docs)


def test_two_guides_on_same_page_are_separate_and_stubs_are_not_guides(tmp_path):
    first = _lines()[:19]
    second = _lines(number="07.16.26111.0000002-0", code="2172", tax="COFINS")[:19]
    path = _write_pages(tmp_path, [first + second])
    docs = _docs(_run(path))
    assert len(docs) == 2 and docs[0].page_numbers == docs[1].page_numbers == (1,)
    assert docs[0].block_numbers != docs[1].block_numbers


def test_same_number_repeated_block_deduplicates_revenues_preserves_occurrences(tmp_path):
    result = _run(_write_pages(tmp_path, [_lines(), _lines()]))
    doc, = _docs(result)
    assert len(doc.revenues) == 1 and doc.page_numbers == (1, 2)
    assert "DARF_REPEATED_DOCUMENT_BLOCK" in result.warnings


def test_same_number_continuation_with_explicit_identical_header_merges_revenues(tmp_path):
    result = _run(_write_pages(tmp_path, [_lines(total="2.481,12"), _lines(total="2.481,12", code="2172", tax="COFINS")]))
    doc, = _docs(result)
    assert len(doc.revenues) == 2 and doc.validation.sum_matches_total is True
    assert "DARF_REVENUE_TOTAL_MISMATCH" not in result.warnings


def test_same_number_different_header_does_not_merge(tmp_path):
    result = _run(_write_pages(tmp_path, [_lines(), _lines(total="0,00", values="0,00 0,00")]))
    assert len(_docs(result)) == 2
    assert "DARF_DOCUMENT_NUMBER_CONFLICT" in result.warnings


@pytest.mark.parametrize("description,tax,source", (("CONTRIBUICAO DESCONHECIDA", "UNKNOWN", None), ("PIS SINTETICO", "PIS", "DESCRIPTION")))
def test_unknown_code_is_preserved_without_filename_guess(tmp_path, description, tax, source):
    result = _run(_write(tmp_path, code="9099", tax=description))
    row = _docs(result)[0].revenues[0]
    assert row.revenue_code == "9099" and row.tax == tax and row.tax_identification_source == source
    assert description in row.description and "DARF_REVENUE_CODE_UNKNOWN" in result.warnings


def test_conflicting_code_and_description_is_not_hidden():
    assert identify_tax("8109", "COFINS") == ("PIS", "REVENUE_CODE", "DARF_TAX_CODE_DESCRIPTION_CONFLICT")


def test_observed_code_with_extension_is_preserved_and_mapped_by_base(tmp_path):
    doc, = _docs(_run(_write(tmp_path, code="8109-01")))
    assert doc.revenues[0].revenue_code == "8109-01"
    assert doc.revenues[0].code_extension == "01" and doc.revenues[0].tax == "PIS"


def test_month_and_date_both_explicit_are_preserved_without_inventing_month(tmp_path):
    doc, = _docs(_run(_write(tmp_path, header_period="30/06/2026")))
    assert doc.header.observed_header_period.kind is PeriodKind.DATE
    assert doc.header.observed_header_period.month is None
    assert doc.header.assessment_period.month == "2026-06"
    assert doc.header.assessment_period_source == "REVENUES_CONSENSUS"


def test_multiple_different_revenue_periods_are_not_collapsed(tmp_path):
    lines = _lines()
    index = lines.index("Totais 1.240,56 1.240,56")
    lines[index:index] = ["2172 COFINS 0,00 0,00", "PA:07/2026 Vencimento:24/07/2026"]
    result = _run(_write(tmp_path, lines))
    assert [row.assessment_period.month for row in _docs(result)[0].revenues] == ["2026-06", "2026-07"]
    assert "DARF_ASSESSMENT_PERIOD_MULTIPLE" in result.warnings


def test_missing_revenues_and_values_are_technical_warnings(tmp_path):
    lines = _lines()
    lines[13:16] = []
    result = _run(_write(tmp_path, lines))
    assert result.extraction_status is ExtractionStatus.MATCHED
    assert "DARF_REVENUES_MISSING" in result.warnings
    result = _run(_write(tmp_path, values=""))
    assert "DARF_REVENUE_AMOUNTS_INCOMPLETE" in result.warnings
    assert _docs(result)[0].revenues[0].total_amount is None


def test_debt_active_federal_content_and_mixed_family_bundle_are_unsupported(tmp_path):
    path = _write(tmp_path, tax="DIV.ATIVA-CONTRIBUICAO SINTETICA")
    assert DarfPdfParser().supports(_context(path)) is False
    das = _lines()[:19]
    das[:2] = ["Documento de Arrecadacao do Simples Nacional"]
    assert _run(_write_pages(tmp_path, [_lines(), das])).extraction_status is ExtractionStatus.UNSUPPORTED


def test_declaration_receipt_is_structured_but_never_printed(tmp_path):
    path = _write(tmp_path, observation="No Recibo Declaracao: 12345678901234")
    doc, = _docs(_run(path))
    assert doc.header.declaration_receipt_number == "12345678901234"
    assert "12345678901234" not in json.dumps(sanitized_darf_summary(path))


def test_receipt_is_not_mistaken_for_missing_taxpayer_id(tmp_path):
    lines = [line for line in _lines(observation="No Recibo Declaracao: 12345678901234")
             if not line.startswith("CNPJ")]
    result = _run(_write(tmp_path, lines))
    assert _docs(result)[0].header.taxpayer_id is None
    assert "DARF_TAXPAYER_ID_MISSING" in result.warnings


def test_filename_tax_hint_never_overrides_content_and_provenience_survives(tmp_path):
    path = tmp_path / "PIS 08-2026.pdf"
    write_synthetic_text_pdf(path, _lines(code="2172", tax="COFINS"))
    hint = DocumentSignal(name="classifier_hint", value="PIS", provenance=SignalProvenance.FILENAME, confidence=0.2)
    result = DocumentParserRuntime(default_parser_registry()).run_file(path, context_signals=(hint,))
    assert _docs(result)[0].revenues[0].tax == "COFINS" and hint in result.signals


def test_missing_optional_fields_and_unparsed_period_lower_confidence(tmp_path):
    lines = [line for line in _lines(period="Periodo Especial") if not line.startswith(("CNPJ", "Razao", "Numero do Documento", "Pagar"))]
    result = _run(_write(tmp_path, lines))
    assert result.extraction_status is ExtractionStatus.MATCHED and result.confidence < 1
    assert {"DARF_TAXPAYER_ID_MISSING", "DARF_TAXPAYER_NAME_MISSING", "DARF_DOCUMENT_NUMBER_MISSING",
            "DARF_PAY_UNTIL_MISSING", "DARF_ASSESSMENT_PERIOD_UNPARSED"} <= set(result.warnings)


def test_missing_period_header_does_not_pick_unrelated_dates_and_uses_explicit_revenue_consensus():
    text = "\n".join([
        "Periodo de Apuracao          Data de Vencimento        Numero do Documento",
        "                             24/07/2026               07.16.26111.0000001-0",
        "Observacoes:", "Composicao do Documento de Arrecadacao",
        "8109 PIS 10,00 10,00", "PA:2o Trimestre/2026 Vencimento:24/07/2026",
    ])
    guide = FederalRevenueGuideExtractor().extract(text)
    assert guide.header.observed_header_period is None
    assert guide.header.assessment_period.kind is PeriodKind.QUARTER


@pytest.mark.parametrize("taxpayer,kind,valid", (("CPF: 123.456.789-09", "CPF", True),
                                               ("CNPJ: 11.111.111/1111-11", "CNPJ", False)))
def test_taxpayer_normalization_check_digits(tmp_path, taxpayer, kind, valid):
    lines = _lines()
    lines[2] = taxpayer
    doc, = _docs(_run(_write(tmp_path, lines)))
    assert doc.header.taxpayer_id_kind == kind and doc.header.taxpayer_id_structure_valid is valid
    if not valid:
        assert "DARF_TAXPAYER_ID_INVALID_STRUCTURE" in doc.warning_codes


def test_sum_mismatch_warns_without_rejecting_and_pay_until_is_separate(tmp_path):
    lines = [line.replace("Pagar este documento ate: 24/07/2026", "Pagar este documento ate: 27/07/2026") for line in _lines(total="1.241,56")]
    result = _run(_write(tmp_path, lines))
    assert result.extraction_status is ExtractionStatus.MATCHED
    assert {"DARF_REVENUE_TOTAL_MISMATCH", "DARF_PAY_UNTIL_DIFFERS_FROM_DUE_DATE"} <= set(result.warnings)
    assert _docs(result)[0].header.pay_until == "2026-07-27"


@pytest.mark.parametrize("penalty,interest", (("5,00", ""), ("", "1,00"), ("", "")))
def test_layout_columns_preserve_blank_surcharges_without_shifting(penalty, interest):
    header = f"{'Codigo':<8}{'Denominacao':<48}{'Principal':>15}{'Multa':>15}{'Juros':>15}{'Total':>15}"
    row = f"{'8109':<8}{'PIS SINTETICO':<48}{'100,00':>15}{penalty:>15}{interest:>15}{'106,00':>15}"
    guide = FederalRevenueGuideExtractor().extract("\n".join(["Composicao do Documento de Arrecadacao", header, row, "PA:06/2026 Vencimento:24/07/2026", "Totais 106,00"]))
    revenue, = guide.revenues
    assert revenue.principal_amount == Decimal("100.00")
    assert revenue.penalty_amount == Decimal(penalty.replace(",", ".") or "0.00")
    assert revenue.interest_amount == Decimal(interest.replace(",", ".") or "0.00")
    assert revenue.total_amount == Decimal("106.00")


def test_ambiguous_unaligned_three_amounts_warn_instead_of_shifting(tmp_path):
    result = _run(_write(tmp_path, values="100,00 5,00 105,00", total="105,00"))
    row = _docs(result)[0].revenues[0]
    assert row.penalty_amount is None and row.interest_amount is None
    assert "DARF_REVENUE_AMOUNTS_INCOMPLETE" in result.warnings


@pytest.mark.parametrize("observation", ("PGFN-SISPAR IDENTIFICADOR SINTETICO", "PARC-SN", "PARCSN", "PARCELAMENTO SIMPLIFICADO", "PARCELA 01", "PERT", "RELP", "SIMEI"))
@pytest.mark.parametrize("shell", ("FEDERAL", "DAS"))
def test_installments_are_excluded_by_both_parsers_independent_of_registry_order(tmp_path, observation, shell):
    lines = _lines(observation=observation)
    if shell == "DAS":
        lines[:2] = ["Documento de Arrecadacao do Simples Nacional"]
        lines = lines[:lines.index("SENDA (Versao:1.0.0) Pagina:1/1")]
    path = _write(tmp_path, lines)
    for parser in (DarfPdfParser(), DasPdfParser()):
        assert parser.supports(_context(path)) is False
    assert DarfPdfParser().parse(_context(path)).extraction_status is ExtractionStatus.UNSUPPORTED
    normal_only = DocumentParserRuntime(ParserRegistry((DarfPdfParser(), DasPdfParser()))).run_file(path)
    assert normal_only.extraction_status is ExtractionStatus.UNSUPPORTED
    production = DocumentParserRuntime(default_parser_registry()).run_file(path)
    if observation in {"PARC-SN", "PARCELA 01"}:
        assert production.extraction_status is ExtractionStatus.UNSUPPORTED
    else:
        assert production.extraction_status is ExtractionStatus.MATCHED
        assert production.document_family == "INSTALLMENT"


@pytest.mark.parametrize("observation", ("", "IC"))
def test_ordinary_das_is_not_darf_in_either_registry_order(tmp_path, observation):
    lines = _lines(observation=observation)
    lines[:2] = ["Documento de Arrecadacao do Simples Nacional"]
    lines = lines[:lines.index("SENDA (Versao:1.0.0) Pagina:1/1")]
    path = _write(tmp_path, lines)
    assert DarfPdfParser().supports(_context(path)) is False and DasPdfParser().supports(_context(path)) is True
    for registry in (default_parser_registry(), ParserRegistry((DarfPdfParser(), DasPdfParser()))):
        assert DocumentParserRuntime(registry).run_file(path).document_family == "DAS"


@pytest.mark.parametrize("lines", (["Receita Federal CNPJ Valor Vencimento"],
                                    ["Documento de Arrecadacao de Receitas Federais", "DARF", "Periodo de Apuracao:06/2026", "Valor Total:100,00"],
                                    ["Documento de Arrecadacao de Receitas Estaduais", "DARE ICMS", "Valor 100,00"],
                                    ["CONTEUDO SINTETICO ALEATORIO"]))
def test_weak_signatures_state_guides_and_filename_darf_do_not_match(tmp_path, lines):
    path = tmp_path / "DARF PIS 08-2026.pdf"
    write_synthetic_text_pdf(path, lines)
    assert DarfPdfParser().supports(_context(path)) is False
    assert _run(path).extraction_status is ExtractionStatus.UNSUPPORTED


def test_unknown_or_blank_page_in_bundle_is_not_silently_ignored(tmp_path):
    for extra in ([], ["DOCUMENTO INDEPENDENTE DESCONHECIDO"]):
        assert _run(_write_pages(tmp_path, [_lines(), extra])).extraction_status is ExtractionStatus.UNSUPPORTED


def test_federal_layout_extractor_is_reusable_without_darf_acceptance(tmp_path):
    lines = _lines(observation="PGFN-SISPAR IDENTIFICADOR SINTETICO")
    guide = FederalRevenueGuideExtractor().extract("\n".join(lines))
    assert guide.header.taxpayer_id and guide.revenues[0].revenue_code == "8109"
    assert guide.revenues[0].tax == "UNKNOWN"  # Classifier, not layout, owns taxonomy.
    assert DarfPdfParser().supports(_context(_write(tmp_path, lines))) is False


def test_blank_corrupt_and_unexpected_error_are_sanitized(tmp_path, monkeypatch):
    assert _run(_write(tmp_path, [])).extraction_status is ExtractionStatus.INCONCLUSIVE
    corrupt = tmp_path / "corrupt.pdf"
    corrupt.write_bytes(b"%PDF-1.4\nsynthetic-corruption")
    assert _run(corrupt).extraction_status is ExtractionStatus.INVALID
    def broken(*args, **kwargs):
        raise RuntimeError("SENSITIVE SYNTHETIC CONTENT must not escape")
    monkeypatch.setattr(FederalRevenueGuideExtractor, "extract", broken)
    result = _run(_write(tmp_path))
    assert result.extraction_status is ExtractionStatus.ERROR and result.warnings == ("DARF_EXTRACTION_ERROR",)
    assert "SENSITIVE" not in result.model_dump_json()


def test_sanitized_probe_is_read_only_and_never_outputs_values_identifiers_or_path(tmp_path):
    path = _write(tmp_path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    summary = sanitized_darf_summary(path)
    assert summary["family"] == "DARF" and summary["matched"] is True
    assert summary["documents_count"] == summary["revenues_count"] == 1
    assert summary["taxes"] == ["PIS"] and summary["warning_codes"] == []
    assert summary["sum_matches_total"] is True
    serialized = json.dumps(summary)
    for secret in ("12345678000195", "EMPRESA SINTETICA", "1240.56", "26111", "85870000000", str(path)):
        assert secret not in serialized
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_darf_parser_run_replay_is_idempotent_without_mutating_canonical_evidence(tmp_path, db_session):
    organization = Organization(name="Synthetic DARF Parser", slug="synthetic-darf-parser")
    db_session.add(organization)
    db_session.flush()
    evidence = FiscalEvidence(organization_id=organization.id, source="WATCHER_FILE", source_type="WATCHER_INGEST",
                              file_hash=f"{organization.id:064x}"[-64:], status="PENDENTE")
    db_session.add(evidence)
    db_session.flush()
    columns = ("detected_tax", "detected_obligation", "cnpj_detected", "competencia_detected", "confidence",
               "company_id", "period_id", "amount_total", "due_date")
    before = {column: getattr(evidence, column) for column in columns}
    obligations = db_session.scalar(select(func.count()).select_from(FiscalObligationStatus))
    payload = WatcherParserRunRequest.model_validate(_run(_write(tmp_path)).to_backend_payload())
    first = register_document_parser_run(db_session, organization=organization, evidence_id=evidence.id, payload=payload)
    replay = register_document_parser_run(db_session, organization=organization, evidence_id=evidence.id, payload=payload)
    assert first.created and not replay.created and first.parser_run.id == replay.parser_run.id
    assert db_session.scalar(select(func.count()).select_from(FiscalDocumentParserRun)) == 1
    assert db_session.scalar(select(func.count()).select_from(FiscalObligationStatus)) == obligations
    db_session.refresh(evidence)
    assert {column: getattr(evidence, column) for column in columns} == before
