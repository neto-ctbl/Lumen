from __future__ import annotations

from decimal import Decimal
import hashlib
import json

import fitz
import pytest
from sqlalchemy import func, select

from agent.parsers.contracts import DocumentContext, DocumentSignal, ExtractionStatus, SignalProvenance, TechnicalFormat
from agent.parsers.darf_pdf import DarfPdfParser
from agent.parsers.das_pdf import DasPdfParser
from agent.parsers.runtime import DocumentParserRuntime, ParserRegistry, default_parser_registry
from agent.parsers.state_guide_pdf import STATE_PARSER_NAME, StateGuideFile, StateGuidePdfParser
from agent.parsers.state_guide_probe import sanitized_state_summary
from agent.parsers.state_revenue_codes import STATE_REVENUE_CODES, classify_state_revenue
from agent.parsers.state_revenue_guide import StateRevenueGuideExtractor
from backend.app.models.fiscal_document_parser_run import FiscalDocumentParserRun
from backend.app.models.fiscal_evidence import FiscalEvidence
from backend.app.models.fiscal_obligation_status import FiscalObligationStatus
from backend.app.models.organization import Organization
from backend.app.schemas.watcher import WatcherParserRunRequest
from backend.app.services.document_parser_runs import register_document_parser_run


def _columns(*items):
    line = ""
    for position, value in items:
        line = line.ljust(position) + value
    return line


def _lines(*, code="108", description="NORMAL", number="900000000000001", reference="300-Mensal - 06/2026",
           total="106,00", principal="100,00", penalty="5,00", interest="1,00", installment="-", taxpayer=True):
    lines = [
        "ESTADO DE GOIAS", "SECRETARIA DA ECONOMIA", "TESOURO ESTADUAL",
        f"DOCUMENTO DE ARRECADACAO DE RECEITAS ESTADUAIS - DARE 5.1    No {number}",
        _columns((0, "Contribuinte"), (100, "Inscricao Estadual: 999.00000-0")),
        "EMPRESA SINTETICA LTDA",
    ]
    if taxpayer:
        lines.append("CNPJ: 12.345.678/0001-95")
    lines += [
        _columns((0, "Endereco"), (60, "Municipio"), (90, "UF"), (100, "DDD/Telefone")),
        _columns((0, "ENDERECO SINTETICO"), (60, "CIDADE SINTETICA"), (90, "GO"), (100, "-")),
        _columns((0, "Receita"), (95, "Alineas"), (140, "Valores (R$)")),
    ]
    if code != "4014":
        lines.append("1 - ICMS - IMPOSTO SINTETICO")
    lines.append(_columns((0, f"{code} - {description}"), (100, f"Valor Original (900001) {principal}")))
    if penalty is not None:
        lines.append(_columns((100, f"Multa (900002) {penalty}")))
    if interest is not None:
        lines.append(_columns((100, f"Juros (900003) {interest}")))
    lines += [
        _columns((0, "Documento de Origem"), (40, "Data de Vencimento"), (70, "Condicao")),
        _columns((0, "-"), (40, "20/07/2026"), (70, "4000")),
        _columns((0, "Referencia"), (40, "Parcela")),
        _columns((0, reference), (40, installment)),
        "Validade do: 25/07/2026", f"Total a recolher: {total}",
        "Informacoes complementares:",
    ]
    return lines


def _write(tmp_path, pages=None, filename="arquivo-neutro.pdf", **kwargs):
    path = tmp_path / filename
    with fitz.open() as pdf:
        for lines in pages if pages is not None else [_lines(**kwargs)]:
            page = pdf.new_page(width=1000, height=1300)
            for index, line in enumerate(lines):
                page.insert_text((25, 30 + index * 15), line, fontsize=7, fontname="cour")
        pdf.save(str(path))
    return path


def _context(path):
    return DocumentContext(file_path=path, technical_format=TechnicalFormat.PDF)


def _run(path):
    return DocumentParserRuntime(default_parser_registry()).run_file(path)


def _docs(result):
    return StateGuideFile.model_validate(result.structured_data).documents


@pytest.mark.parametrize("code,description,kind,tax", (
    ("108", "NORMAL", "ICMS", "ICMS"),
    ("4502", "ICMS DIFAL Simples Nacional - Comercializacao", "DIFAL", "ICMS"),
    ("159", "ICMS Diferencial de Aliquotas - Uso/Consumo/Ativo Imobilizado", "DIFAL_CONSUMPTION_ASSET", "ICMS"),
    ("4014", "CONTRIBUICOES AO PROTEGE", "PROTEGE", "STATE_REVENUE"),
))
def test_known_codes_neutral_filename_decimal_fields_and_semantic_support(tmp_path, code, description, kind, tax):
    path = _write(tmp_path, code=code, description=description)
    result = _run(path)
    assert result.parser_name == STATE_PARSER_NAME and result.parser_version == "1"
    assert result.document_family == "STATE_GUIDE" and result.extraction_status is ExtractionStatus.MATCHED
    assert result.warnings == () and result.confidence == 1
    doc, = _docs(result)
    assert doc.guide_kind == kind and doc.header.layout == "DARE_GO_5_1"
    assert doc.header.taxpayer_id == "12345678000195" and doc.header.taxpayer_id_structure_valid is True
    assert doc.header.state_registration == "999.00000-0" and doc.header.uf == doc.header.taxpayer_uf == "GO"
    assert doc.header.taxpayer_name == "EMPRESA SINTETICA LTDA"
    assert doc.header.reference_label == "300-Mensal - 06/2026"
    assert doc.header.reference_frequency_code == "300"
    assert doc.header.reference_period.month == "2026-06" and doc.header.reference_period_source == "CONTENT_REFERENCE"
    assert doc.header.due_date == "2026-07-20" and doc.header.pay_until == "2026-07-25"
    assert doc.header.condition_code == "4000" and doc.header.origin_document is None
    assert doc.header.document_number == "900000000000001" and doc.header.total_amount == Decimal("106.00")
    row, = doc.revenues
    assert row.revenue_code == code and row.tax == tax and row.guide_kind == kind
    assert row.classification_source == "REVENUE_CODE"
    assert row.principal_amount == Decimal("100.00") and row.penalty_amount == Decimal("5.00")
    assert row.interest_amount == Decimal("1.00") and row.total_amount == Decimal("106.00")
    assert len(row.components) == 3 and doc.validation.sum_matches_total is True
    assert doc.validation.pay_until_matches_due_date is False  # Distinct, not a fiscal error.
    assert result.structured_data["documents"][0]["header"]["total_amount"] == "106.00"
    assert doc.page_numbers == (1,) and doc.block_numbers == (1,)
    assert DasPdfParser().supports(_context(path)) is False and DarfPdfParser().supports(_context(path)) is False


def test_mapping_is_empirical_and_normal_code_needs_icms_context():
    assert set(STATE_REVENUE_CODES) == {"108", "4502", "159", "4014"}
    assert classify_state_revenue("108", "NORMAL")[1] == "UNKNOWN"
    assert classify_state_revenue("41", "CONTRIBUICAO")[1] == "UNKNOWN"


def test_protege_parent_and_subordinate_code_are_one_revenue_not_two(tmp_path):
    lines = _lines(code="4014", description="CONTRIBUICOES AO PROTEGE")
    index = next(i for i, line in enumerate(lines) if "Documento de Origem" in line)
    lines[index:index] = ["41 - CONTRIBUICAO"]
    result = _run(_write(tmp_path, [lines]))
    doc, = _docs(result)
    row, = doc.revenues
    assert row.parent_revenue_code == "4014" and row.revenue_code == "41"
    assert row.guide_kind == doc.guide_kind == "PROTEGE"
    assert row.classification_source == "PARENT_AND_REVENUE_CODE"
    assert len(row.components) == 3 and doc.validation.sum_matches_total is True
    assert "STATE_REVENUE_CODE_UNKNOWN" not in result.warnings
    assert sanitized_state_summary(_write(tmp_path, [lines]))["revenue_codes_known_count"] == 1


@pytest.mark.parametrize("code,description,kind", (
    ("9999", "RECEITA DESCONHECIDA", "UNKNOWN"),
    ("9999", "ICMS DIFAL", "DIFAL"),
    ("9999", "ICMS Diferencial de Aliquotas", "DIFAL"),
    ("9999", "ICMS DIFAL Uso/Consumo", "DIFAL_CONSUMPTION_ASSET"),
    ("9999", "CONTRIBUICAO AO PROTEGE", "PROTEGE"),
))
def test_unknown_code_is_preserved_with_conservative_description_fallback(tmp_path, code, description, kind):
    result = _run(_write(tmp_path, code=code, description=description, filename="PROTEGE DIFAL 08-2026.pdf"))
    doc, = _docs(result)
    row, = doc.revenues
    assert result.extraction_status is ExtractionStatus.MATCHED and row.revenue_code == code
    assert row.guide_kind == doc.guide_kind == kind
    assert "STATE_REVENUE_CODE_UNKNOWN" in result.warnings
    assert row.classification_source == ("DESCRIPTION" if kind != "UNKNOWN" else None)


@pytest.mark.parametrize("code,description", (("4502", "PROTEGE"), ("159", "ICMS DIFAL"), ("9999", "PROTEGE ICMS DIFAL")))
def test_conflicting_code_description_or_multiple_descriptions_are_unknown(tmp_path, code, description):
    result = _run(_write(tmp_path, code=code, description=description))
    assert _docs(result)[0].guide_kind == "UNKNOWN"
    assert "STATE_REVENUE_CLASSIFICATION_CONFLICT" in result.warnings


def test_no_taxpayer_id_or_surcharges_in_actual_shell_remain_null(tmp_path):
    result = _run(_write(tmp_path, taxpayer=False, penalty=None, interest=None, total="100,00"))
    doc, = _docs(result)
    assert doc.header.taxpayer_id is None and doc.header.taxpayer_id_structure_valid is None
    assert doc.revenues[0].penalty_amount is None and doc.revenues[0].interest_amount is None
    assert doc.validation.sum_matches_total is True and "STATE_TAXPAYER_ID_MISSING" in result.warnings


@pytest.mark.parametrize("principal,penalty,interest,total,matches", (
    ("0,00", "0,00", "0,00", "0,00", True),
    ("1.000,00", "20,00", "1,99", "1.021,99", True),
    ("100,00", "5,00", "1,00", "107,00", False),
))
def test_zero_amounts_and_components_total_warning_only(tmp_path, principal, penalty, interest, total, matches):
    result = _run(_write(tmp_path, principal=principal, penalty=penalty, interest=interest, total=total))
    assert result.extraction_status is ExtractionStatus.MATCHED
    assert _docs(result)[0].validation.sum_matches_total is matches
    assert ("STATE_COMPONENT_TOTAL_MISMATCH" in result.warnings) is (not matches)


@pytest.mark.parametrize("reference,kind,month", (
    ("300-Mensal - 06/2026", "MONTH", "2026-06"),
    ("2o Trimestre/2026", "QUARTER", None),
    ("30/06/2026", "DATE", None),
    ("01/04/2026 a 30/06/2026", "RANGE", None),
    ("REF SINTETICA ESPECIAL", "UNKNOWN", None),
))
def test_content_period_semantics_and_provenance_never_overridden_by_hints(tmp_path, reference, kind, month):
    path = _write(tmp_path, reference=reference, filename="ICMS 08-2026.pdf")
    hint = DocumentSignal(name="period_from_path", provenance=SignalProvenance.PATH, confidence=0.1, value="2026-08")
    result = DocumentParserRuntime(default_parser_registry()).run_file(path, context_signals=(hint,))
    pa = _docs(result)[0].header.reference_period
    assert pa.kind == kind and pa.month == month and hint in result.signals
    content = next(s for s in result.signals if s.name == "period_from_content")
    assert content.provenance is SignalProvenance.CONTENT and content.value[0]["source"] == "CONTENT_REFERENCE"
    assert content.value[0]["period"]["month"] == month


def test_optional_absent_fields_are_null_not_guessed_from_numbers(tmp_path):
    lines = [line.partition("Inscricao Estadual")[0].rstrip() for line in _lines(taxpayer=False) if not any(label in line for label in (
        "CNPJ", "Referencia", "300-Mensal", "Validade do",
    ))]
    result = _run(_write(tmp_path, [lines]))
    header = _docs(result)[0].header
    assert header.state_registration is header.taxpayer_id is header.reference_period is header.pay_until is None
    assert "STATE_REFERENCE_MISSING" in result.warnings


@pytest.mark.parametrize("identifier,expected_kind,valid", (
    ("12.345.678/0001-95", "CNPJ", True), ("11111111111111", "CNPJ", False),
    ("529.982.247-25", "CPF", True), ("11111111111", "CPF", False),
))
def test_labeled_taxpayer_ids_only_and_structural_warning(tmp_path, identifier, expected_kind, valid):
    lines = _lines(taxpayer=False)
    lines.insert(6, f"CNPJ/CPF: {identifier}")
    result = _run(_write(tmp_path, [lines]))
    header = _docs(result)[0].header
    assert header.taxpayer_id_kind == expected_kind and header.taxpayer_id_structure_valid is valid
    assert ("STATE_TAXPAYER_ID_INVALID" in result.warnings) is (not valid)


def test_multiple_components_and_revenues_belong_to_one_document(tmp_path):
    lines = _lines(total="116,00")
    index = next(i for i, line in enumerate(lines) if "Documento de Origem" in line)
    lines[index:index] = [_columns((0, "4014 - CONTRIBUICOES AO PROTEGE"), (100, "Valor Original (900004) 10,00"))]
    result = _run(_write(tmp_path, [lines]))
    doc, = _docs(result)
    assert len(doc.revenues) == 2 and len(doc.revenues[0].components) == 3
    assert {row.guide_kind for row in doc.revenues} == {"ICMS", "PROTEGE"}
    assert doc.guide_kind == "UNKNOWN" and "STATE_MULTIPLE_GUIDE_KINDS" in result.warnings
    assert doc.validation.sum_matches_total is True


def test_two_independent_guides_on_pages_keep_all_identity_period_total_and_locators(tmp_path):
    result = _run(_write(tmp_path, [_lines(), _lines(number="900000000000002", reference="07/2026", total="0,00",
                                                   principal="0,00", penalty="0,00", interest="0,00")]))
    first, second = _docs(result)
    assert first.header.document_number != second.header.document_number
    assert first.header.reference_period.month == "2026-06" and second.header.reference_period.month == "2026-07"
    assert first.header.total_amount == Decimal("106.00") and second.header.total_amount == Decimal("0.00")
    assert first.page_numbers == (1,) and second.page_numbers == (2,)


def test_two_independent_guides_on_one_page_are_not_grouped(tmp_path):
    first, second = _docs(_run(_write(tmp_path, [_lines() + _lines(number="900000000000002")])) )
    assert first.page_numbers == second.page_numbers == (1,) and first.block_numbers != second.block_numbers


def test_bank_and_taxpayer_copies_are_one_document_and_blank_parcela_not_installment(tmp_path):
    lines = _lines()
    bank = lines[:6] + ["Validade do: 25/07/2026", "Total a recolher: 106,00"]
    doc, = _docs(_run(_write(tmp_path, [bank + lines])))
    assert len(doc.revenues) == 1 and doc.header.installment_reference is None


def test_bank_copy_with_different_number_is_not_silently_dropped(tmp_path):
    bank = _lines(number="900000000000002")[:6] + ["Validade do: 25/07/2026", "Total a recolher: 106,00"]
    assert _run(_write(tmp_path, [bank + _lines()])).extraction_status is ExtractionStatus.UNSUPPORTED


def test_explicit_exact_repeat_deduplicates_but_preserves_physical_locators(tmp_path):
    result = _run(_write(tmp_path, [_lines(), _lines()]))
    doc, = _docs(result)
    assert len(doc.revenues) == 1 and doc.page_numbers == (1, 2)
    assert "STATE_REPEATED_DOCUMENT_BLOCK" in result.warnings


def test_same_number_different_content_not_guessed_to_be_continuation(tmp_path):
    result = _run(_write(tmp_path, [_lines(), _lines(total="107,00")]))
    assert len(_docs(result)) == 2 and "STATE_DOCUMENT_NUMBER_CONFLICT" in result.warnings


@pytest.mark.parametrize("marker", ("PARCELAMENTO SEFAZ", "ACORDO SINTETICO", "PARCELA 01", "PARCELAS", "PGFN", "PERT", "RELP"))
def test_explicit_installment_in_any_body_location_is_unsupported(tmp_path, marker):
    lines = _lines() + [marker]
    path = _write(tmp_path, [lines])
    parser = StateGuidePdfParser()
    assert parser.supports(_context(path)) is False
    assert parser.parse(_context(path)).extraction_status is ExtractionStatus.UNSUPPORTED
    assert _run(path).extraction_status is ExtractionStatus.UNSUPPORTED
    extracted = StateRevenueGuideExtractor().extract("\n".join(lines))
    assert extracted.header.document_number and extracted.revenues[0].tax == "UNKNOWN"


@pytest.mark.parametrize("installment", ("01", "ACORDO 900001", "PARCELA 02"))
def test_filled_installment_cell_is_unsupported_without_program_classification(tmp_path, installment):
    assert _run(_write(tmp_path, installment=installment)).extraction_status is ExtractionStatus.UNSUPPORTED


@pytest.mark.parametrize("extra", ([], ["DOCUMENTO INDEPENDENTE DESCONHECIDO"]))
def test_unknown_blank_or_mixed_page_is_not_ignored(tmp_path, extra):
    assert _run(_write(tmp_path, [_lines(), extra])).extraction_status is ExtractionStatus.UNSUPPORTED


@pytest.mark.parametrize("lines", (
    ["CONTEUDO ALEATORIO"],
    ["Documento de Arrecadacao do Simples Nacional", "DAS"],
    ["Documento de Arrecadacao de Receitas Federais", "DARF"],
    ["PGFN SISPAR PARCELAMENTO"],
    ["PREFEITURA MUNICIPAL", "ISSQN", "DARE"],
    ["DOCUMENTO DE ARRECADACAO DE RECEITAS ESTADUAIS", "ICMS", "GO"],
))
def test_filename_and_weak_nonstate_shell_never_match(tmp_path, lines):
    path = _write(tmp_path, [lines], filename="ICMS DIFAL PROTEGE 06-2026.pdf")
    assert StateGuidePdfParser().supports(_context(path)) is False
    assert _run(path).extraction_status is ExtractionStatus.UNSUPPORTED


def test_municipal_content_in_state_shell_excluded(tmp_path):
    assert _run(_write(tmp_path, [_lines() + ["PREFEITURA MUNICIPAL ISS"]])).extraction_status is ExtractionStatus.UNSUPPORTED


def test_registry_order_is_not_the_state_semantic_guard(tmp_path):
    path = _write(tmp_path)
    for parsers in ((StateGuidePdfParser(), DasPdfParser(), DarfPdfParser()),
                    (DarfPdfParser(), StateGuidePdfParser(), DasPdfParser())):
        assert DocumentParserRuntime(ParserRegistry(parsers)).run_file(path).document_family == "STATE_GUIDE"
    assert DocumentParserRuntime().run_file(path).extraction_status is ExtractionStatus.UNSUPPORTED


def test_no_text_corrupt_wrong_format_and_exception_sanitization(tmp_path, monkeypatch):
    assert _run(_write(tmp_path, [[]])).extraction_status is ExtractionStatus.INCONCLUSIVE
    corrupt = tmp_path / "corrupt.pdf"
    corrupt.write_bytes(b"%PDF-1.4\nsynthetic-corruption")
    assert _run(corrupt).extraction_status is ExtractionStatus.INVALID
    assert StateGuidePdfParser().parse(_context(corrupt)).extraction_status is ExtractionStatus.INVALID
    context = DocumentContext(file_path=corrupt, technical_format=TechnicalFormat.JSON)
    assert StateGuidePdfParser().supports(context) is False
    assert StateGuidePdfParser().parse(context).extraction_status is ExtractionStatus.UNSUPPORTED
    def broken(*args, **kwargs):
        raise RuntimeError("SENSITIVE SYNTHETIC CONTENT")
    monkeypatch.setattr(StateRevenueGuideExtractor, "extract", broken)
    result = _run(_write(tmp_path))
    assert result.extraction_status is ExtractionStatus.ERROR and result.warnings == ("STATE_EXTRACTION_ERROR",)
    assert "SENSITIVE" not in result.model_dump_json()


def test_probe_allowlist_and_hash_preserved(tmp_path):
    path = _write(tmp_path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    summary = sanitized_state_summary(path)
    assert summary["family"] == "STATE_GUIDE" and summary["matched"] is True
    assert summary["guide_kinds"] == ["ICMS"] and summary["sum_matches_total"] is True
    serialized = json.dumps(summary)
    for value in ("12345678000195", "999.00000-0", "EMPRESA SINTETICA", "106.00", "900000000000001", str(path)):
        assert value not in serialized
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_state_parser_run_replay_idempotent_no_canonical_mutation(tmp_path, db_session):
    organization = Organization(name="Synthetic State Parser", slug="synthetic-state-parser")
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


def test_document_and_metadata_limits_never_silently_truncate(tmp_path, monkeypatch):
    from agent.parsers.guide_common import PdfPages
    import agent.parsers.state_guide_pdf as module
    text = "\n".join(_lines())
    monkeypatch.setattr(module, "read_pdf_pages", lambda path: PdfPages(ExtractionStatus.MATCHED, (text,) * 65))
    result = StateGuidePdfParser().parse(_context(tmp_path / "synthetic.pdf"))
    assert result.extraction_status is ExtractionStatus.INCONCLUSIVE and result.warnings == ("STATE_DOCUMENT_LIMIT",)
    extracted = StateRevenueGuideExtractor().extract(text)
    oversized = extracted.model_copy(update={"revenues": (extracted.revenues[0].model_copy(update={"description": "X" * 70_000}),)})
    monkeypatch.setattr(module, "read_pdf_pages", lambda path: PdfPages(ExtractionStatus.MATCHED, (text,)))
    monkeypatch.setattr(StateRevenueGuideExtractor, "extract", lambda self, text: oversized)
    result = StateGuidePdfParser().parse(_context(tmp_path / "synthetic.pdf"))
    assert result.extraction_status is ExtractionStatus.INCONCLUSIVE and result.warnings == ("STATE_METADATA_LIMIT",)


def test_actual_state_guide_with_das_darf_bundle_is_not_partially_accepted(tmp_path):
    from backend.tests.test_darf_pdf_parser import _lines as federal_lines
    lines = federal_lines()
    path = _write(tmp_path, [_lines(), lines])
    assert _run(path).extraction_status is ExtractionStatus.UNSUPPORTED


@pytest.mark.parametrize("label,value,warning", (
    ("Data de Vencimento", "31/02/2026", "STATE_DUE_DATE_MISSING_OR_INVALID"),
    ("Validade do", "31/02/2026", "STATE_PAY_UNTIL_INVALID"),
))
def test_invalid_dates_not_inferred_from_reference_or_filename(tmp_path, label, value, warning):
    lines = _lines()
    if label == "Data de Vencimento":
        lines = [line.replace("20/07/2026", value) for line in lines]
    else:
        lines = [line.replace("25/07/2026", value) for line in lines]
    result = _run(_write(tmp_path, [lines]))
    header = _docs(result)[0].header
    assert (header.due_date if label == "Data de Vencimento" else header.pay_until) is None
    assert warning in result.warnings


def _validation_args(tmp_path):
    import argparse
    path = tmp_path / "synthetic.pdf"
    return argparse.Namespace(icms=path, difal=path, difal_consumption_asset=[path], protege=path,
                              das=path, darf=path, sefaz_installment=path)


def test_real_validator_fail_fast_no_pass_after_error_and_sanitized_exception(tmp_path, monkeypatch, capsys):
    import agent.parsers.state_guide_validation as module
    monkeypatch.setattr(module, "database_snapshot", lambda: ((0,), ("20260911_0019",), ("synthetic",)))
    calls = []
    def check(path, family, kind):
        calls.append(kind)
        if kind == "DIFAL":
            raise RuntimeError("SENSITIVE SYNTHETIC VALUE")
    monkeypatch.setattr(module, "_check_file", check)
    assert module.run_validation(_validation_args(tmp_path)) == 1
    assert calls == ["ICMS", "DIFAL"]
    output = capsys.readouterr().out
    assert "ICMS=PASS" in output and "REAL_STATE_GUIDE_VALIDATION=FAIL" in output
    assert "PROTEGE=PASS" not in output and "SENSITIVE" not in output


def test_real_validator_missing_sample_is_failure_not_fake_success(tmp_path, monkeypatch, capsys):
    import agent.parsers.state_guide_validation as module
    monkeypatch.setattr(module, "database_snapshot", lambda: ((0,), ("20260911_0019",), ("synthetic",)))
    monkeypatch.setattr(module, "_check_file", lambda *args: None)
    args = _validation_args(tmp_path)
    args.sefaz_installment = None
    assert module.run_validation(args) == 1
    output = capsys.readouterr().out
    assert "SEFAZ_INSTALLMENT_NEGATIVE_SAMPLE_MISSING" in output
    assert "SEFAZ_INSTALLMENT_NEGATIVE=PASS" not in output and "REAL_STATE_GUIDE_VALIDATION=PASS" not in output


def test_real_validator_detects_database_change_and_never_emits_final_pass(tmp_path, monkeypatch, capsys):
    import agent.parsers.state_guide_validation as module
    snapshots = iter([((0,), ("20260911_0019",), ("before",)), ((0,), ("20260911_0019",), ("after",))])
    monkeypatch.setattr(module, "database_snapshot", lambda: next(snapshots))
    monkeypatch.setattr(module, "_check_file", lambda *args: None)
    assert module.run_validation(_validation_args(tmp_path)) == 1
    output = capsys.readouterr().out
    assert "DATABASE_CHANGED" in output and "REAL_STATE_GUIDE_VALIDATION=PASS" not in output


def test_real_validator_all_checks_success(tmp_path, monkeypatch, capsys):
    import agent.parsers.state_guide_validation as module
    monkeypatch.setattr(module, "database_snapshot", lambda: ((0,), ("20260911_0019",), ("synthetic",)))
    monkeypatch.setattr(module, "_check_file", lambda *args: None)
    assert module.run_validation(_validation_args(tmp_path)) == 0
    assert capsys.readouterr().out.endswith("REAL_STATE_GUIDE_VALIDATION=PASS\n")


def test_real_validator_checks_hash_even_when_content_check_fails(tmp_path, monkeypatch):
    import agent.parsers.state_guide_validation as module
    path = _write(tmp_path)
    before = module.file_digest(path)
    digests = []
    original = module.file_digest
    def digest(candidate):
        digests.append(candidate)
        return original(candidate)
    monkeypatch.setattr(module, "file_digest", digest)
    with pytest.raises(AssertionError):
        module._check_file(path, "STATE_GUIDE", "DIFAL")
    assert len(digests) == 2 and original(path) == before


def test_charge_words_in_tax_description_do_not_replace_alinea_kind(tmp_path):
    result = _run(_write(tmp_path, description="NORMAL - MULTA SINTETICA"))
    row = _docs(result)[0].revenues[0]
    assert row.principal_amount == Decimal("100.00") and row.penalty_amount == Decimal("5.00")


def test_multiple_labeled_charges_on_same_row_keep_each_amount(tmp_path):
    lines = _lines()
    lines = [line for line in lines if "Multa (" not in line and "Juros (" not in line]
    lines = [line.replace("100,00", "100,00 Multa (900002) 5,00 Juros (900003) 1,00") for line in lines]
    row = _docs(_run(_write(tmp_path, [lines])))[0].revenues[0]
    assert len(row.components) == 3 and row.total_amount == Decimal("106.00")


def test_ambiguous_amounts_not_guessed_and_quality_confidence_reduced(tmp_path):
    lines = [line.replace("Valor Original (900001) 100,00", "Valor Original (900001) 100,00 106,00") for line in _lines()]
    result = _run(_write(tmp_path, [lines]))
    assert _docs(result)[0].revenues[0].principal_amount is None and result.confidence < 1
    assert "STATE_COMPONENT_AMOUNT_MISSING_OR_AMBIGUOUS" in result.warnings


def test_first_empty_inline_parcela_does_not_hide_later_installment_marker(tmp_path):
    lines = _lines() + ["Parcela: -", "Parcela 01"]
    assert _run(_write(tmp_path, [lines])).extraction_status is ExtractionStatus.UNSUPPORTED
