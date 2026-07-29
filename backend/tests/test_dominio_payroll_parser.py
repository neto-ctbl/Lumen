from __future__ import annotations

from collections import Counter
from decimal import Decimal
from pathlib import Path

import fitz
import pytest

from backend.app.services.integrations.dominio.contracts import (
    DominioInformedValueKind,
    DominioParserConfidence,
    DominioPayrollBlockType,
    DominioPayrollSectionType,
    DominioPayrollWarningCode,
)
from backend.app.services.integrations.dominio.parser import (
    DominioPayrollNoCompanyBlocksFoundError,
    DominioPayrollTextLayerMissingError,
    parse_dominio_payroll_pages,
    parse_dominio_payroll_pdf,
)
from backend.tests.dominio_test_utils import build_dominio_page


def test_parse_single_company_single_page() -> None:
    pages = [
        build_dominio_page(
            page_label="1/1",
            company_code="0001",
            company_name="EMPRESA FICTICIA ALFA LTDA",
            cnpj="12.345.678/0001-95",
            competencia="05/2026",
            body_lines=[
                "Folha Mensal",
                "PROVENTOS",
                "HORAS NORMAIS 1 1 220:00 1.670,00",
                "PRO-LABORE 100 1 220:00 1.621,00",
                "3.291,00Total:",
                "DESCONTOS",
                "I.N.S.S. 998 1 7,78 155,21",
                "155,21Total:",
                "INFORMATIVA",
                "F.G.T.S DO MES 996 1 0,00 159,58 *",
                "159,58Total:",
                "3.135,79Liquido Geral:",
            ],
        )
    ]

    report = parse_dominio_payroll_pages(pages, source_file_name="Resumo_Mensal_05-2026.pdf")

    assert report.physical_page_count == 1
    assert report.detected_source_competences == ("2026-05",)
    assert report.detected_assessment_competences == ("2026-06",)
    assert len(report.companies) == 1

    company = report.companies[0]
    assert company.dominio_company_code == "0001"
    assert company.company_cnpj == "12345678000195"
    assert company.source_payroll_competence == "2026-05"
    assert company.assessment_competence == "2026-06"
    assert company.has_payroll is True
    assert company.has_employee is True
    assert company.has_pro_labore is True
    assert company.has_inss is True
    assert company.has_fgts is True
    assert company.gross_total == Decimal("3291.00")
    assert company.discount_total == Decimal("155.21")
    assert company.informative_total == Decimal("159.58")
    assert company.net_total == Decimal("3135.79")
    assert company.confidence == DominioParserConfidence.HIGH

    first_rubric = company.rubrics[0]
    assert first_rubric.informed_value_kind == DominioInformedValueKind.HOURS
    assert first_rubric.informed_value_minutes == 13200
    assert company.signal_sources[0].signal == "has_payroll"


def test_parse_groups_multiple_pages_and_continues_section_state() -> None:
    pages = [
        build_dominio_page(
            page_label="1/2",
            company_code="0002",
            company_name="EMPRESA FICTICIA BETA LTDA",
            cnpj="22.345.678/0001-95",
            competencia="05/2026",
            body_lines=[
                "Folha Mensal",
                "PROVENTOS",
                "HORAS NORMAIS 1 4 530:00 4.271,64",
                "4.271,64Total:",
                "DESCONTOS",
                "I.N.S.S. 998 4 62,00 985,81",
            ],
        ),
        build_dominio_page(
            page_label="2/2",
            company_code="0002",
            company_name="EMPRESA FICTICIA BETA LTDA",
            cnpj="22.345.678/0001-95",
            competencia="05/2026",
            body_lines=[
                "985,81Total:",
                "INFORMATIVA",
                "F.G.T.S DO MES 996 4 0,00 981,50 *",
                "981,50Total:",
                "3.285,83Liquido Geral:",
            ],
        ),
    ]

    report = parse_dominio_payroll_pages(pages, source_file_name="Resumo_Mensal_05-2026.pdf")
    company = report.companies[0]

    assert len(report.companies) == 1
    assert company.physical_page_numbers == (1, 2)
    assert company.declared_page_numbers == (1, 2)
    assert company.declared_page_count == 2
    assert company.discount_total == Decimal("985.81")
    assert company.informative_total == Decimal("981.50")
    assert company.net_total == Decimal("3285.83")


def test_parse_supports_multiple_companies_and_file_name_mismatch_warning() -> None:
    pages = [
        build_dominio_page(
            page_label="1/1",
            company_code="0003",
            company_name="EMPRESA FICTICIA GAMMA LTDA",
            cnpj="32.345.678/0001-95",
            competencia="05/2026",
            body_lines=["Folha Mensal", "PROVENTOS", "PRO-LABORE 100 1 220,00 3.483,00", "3.483,00Total:", "3.483,00LÃ­quido Geral:"],
        ),
        build_dominio_page(
            page_label="1/1",
            company_code="0004",
            company_name="EMPRESA FICTICIA DELTA LTDA",
            cnpj="42.345.678/0001-95",
            competencia="05/2026",
            body_lines=["Folha Mensal", "PROVENTOS", "AUTONOMO 235 1 1,00 1.000,00", "1.000,00Total:", "1.000,00LÃ­quido Geral:"],
        ),
    ]

    report = parse_dominio_payroll_pages(pages, source_file_name="Resumo_Mensal_06-2026.pdf")
    warning_codes = Counter(warning.code for warning in report.warnings)

    assert len(report.companies) == 2
    assert warning_codes[DominioPayrollWarningCode.FILE_NAME_COMPETENCE_MISMATCH] == 1


def test_parse_supports_salary_adjustment_and_payment_entry_blocks() -> None:
    pages = [
        build_dominio_page(
            page_label="1/1",
            company_code="0005",
            company_name="EMPRESA FICTICIA EPSILON LTDA",
            cnpj="52.345.678/0001-95",
            competencia="05/2026",
            body_lines=[
                "Folha Mensal",
                "PROVENTOS",
                "HORAS NORMAIS 1 1 220:00 1.670,00",
                "1.670,00Total:",
                "Comp 05/2026 - Alteracao salarial 01/05/2026",
                "PROVENTOS",
                "DIFERENCA DE SALARIOS CCT 8081 3 359,38 359,38",
                "359,38Total:",
                "DESCONTOS",
                "INSS CCT 8092 3 0,00 29,73",
                "29,73Total:",
                "Comp 05/2026 - Data pagto 06/06/2026 - Lancamento",
                "PROVENTOS",
                "DIFERENCA DE SALARIOS 19 1 380,77 380,77",
                "380,77Total:",
                "2.380,42Liquido Geral:",
            ],
        )
    ]

    report = parse_dominio_payroll_pages(pages)
    company = report.companies[0]
    block_types = [block.block_type for block in company.blocks]

    assert DominioPayrollBlockType.MONTHLY_PAYROLL in block_types
    assert DominioPayrollBlockType.SALARY_ADJUSTMENT in block_types
    assert DominioPayrollBlockType.PAYMENT_ENTRY in block_types


def test_parse_preserves_unknown_block_and_warning() -> None:
    pages = [
        build_dominio_page(
            page_label="1/1",
            company_code="0006",
            company_name="EMPRESA FICTICIA ZETA LTDA",
            cnpj="62.345.678/0001-95",
            competencia="05/2026",
            body_lines=[
                "Comp 05/2026 - Evento desconhecido",
                "PROVENTOS",
                "PRO-LABORE 100 1 220,00 3.483,00",
                "3.483,00Total:",
                "3.483,00LÃ­quido Geral:",
            ],
        )
    ]

    report = parse_dominio_payroll_pages(pages)
    company = report.companies[0]
    assert company.blocks[0].block_type == DominioPayrollBlockType.UNKNOWN
    assert any(warning.code == DominioPayrollWarningCode.UNKNOWN_BLOCK_HEADING for warning in company.warnings)


def test_parse_uses_marker_rules_for_section_total_reconciliation() -> None:
    pages = [
        build_dominio_page(
            page_label="1/1",
            company_code="0007",
            company_name="EMPRESA FICTICIA ETA LTDA",
            cnpj="72.345.678/0001-95",
            competencia="05/2026",
            body_lines=[
                "Folha Mensal",
                "DESCONTOS",
                "INSS EMPREGADOR 843 1 11,00 178,31",
                "DEPENDENTE IRRF MENSAL 9176 1 379,18 379,18 *",
                "178,31Total:",
                "INFORMATIVA",
                "F.G.T.S DO MES 996 1 0,00 159,58 *",
                "159,58Total:",
                "2.000,00LÃ­quido Geral:",
            ],
        )
    ]

    report = parse_dominio_payroll_pages(pages)
    company = report.companies[0]
    warning_codes = Counter(warning.code for warning in company.warnings)

    assert warning_codes[DominioPayrollWarningCode.SECTION_TOTAL_MISMATCH] == 0
    deductions = next(section for block in company.blocks for section in block.sections if section.section_type == DominioPayrollSectionType.DEDUCTIONS)
    informational = next(section for block in company.blocks for section in block.sections if section.section_type == DominioPayrollSectionType.INFORMATIONAL)
    assert deductions.calculated_total == Decimal("178.31")
    assert informational.calculated_total == Decimal("159.58")


def test_parse_does_not_mark_employee_for_employer_inss_only_profile() -> None:
    pages = [
        build_dominio_page(
            page_label="1/1",
            company_code="0071",
            company_name="EMPRESA FICTICIA PRO LABORE PURA LTDA",
            cnpj="71.345.678/0001-95",
            competencia="05/2026",
            body_lines=[
                "Folha Mensal",
                "PROVENTOS",
                "PRO-LABORE 100 1 220:00 3.000,00",
                "3.000,00Total:",
                "DESCONTOS",
                "INSS EMPREGADOR 843 1 11,00 330,00",
                "330,00Total:",
                "2.670,00LÃ­quido Geral:",
            ],
        )
    ]

    report = parse_dominio_payroll_pages(pages)
    company = report.companies[0]
    sources = {item.signal: tuple(item.rubric_codes) for item in company.signal_sources if item.value}

    assert company.has_payroll is True
    assert company.has_pro_labore is True
    assert company.has_inss is True
    assert company.has_employee is False
    assert sources["has_pro_labore"] == ("100",)
    assert sources["has_inss"] == ("843",)
    assert "has_employee" not in sources


def test_parse_does_not_mark_employee_for_autonomous_only_profile() -> None:
    pages = [
        build_dominio_page(
            page_label="1/1",
            company_code="0072",
            company_name="EMPRESA FICTICIA AUTONOMA LTDA",
            cnpj="72.345.678/0001-95",
            competencia="05/2026",
            body_lines=[
                "Folha Mensal",
                "PROVENTOS",
                "AUTONOMO 235 1 220:00 1.000,00",
                "1.000,00Total:",
                "DESCONTOS",
                "INSS AUTONOMO 858 1 11,00 110,00",
                "110,00Total:",
                "890,00LÃ­quido Geral:",
            ],
        )
    ]

    report = parse_dominio_payroll_pages(pages)
    company = report.companies[0]
    sources = {item.signal: tuple(item.rubric_codes) for item in company.signal_sources if item.value}

    assert company.has_autonomous is True
    assert company.has_inss is True
    assert company.has_employee is False
    assert sources["has_autonomous"] == ("235", "858")
    assert sources["has_inss"] == ("858",)
    assert "has_employee" not in sources


def test_parse_keeps_employee_sources_free_of_forbidden_codes_when_profile_is_mixed() -> None:
    pages = [
        build_dominio_page(
            page_label="1/1",
            company_code="0073",
            company_name="EMPRESA FICTICIA MISTA LTDA",
            cnpj="73.345.678/0001-95",
            competencia="05/2026",
            body_lines=[
                "Folha Mensal",
                "PROVENTOS",
                "HORAS NORMAIS 1 1 220:00 1.670,00",
                "PRO-LABORE 100 1 220:00 3.000,00",
                "4.670,00Total:",
                "DESCONTOS",
                "INSS EMPREGADOR 843 1 11,00 330,00",
                "I.N.S.S. 998 1 7,78 155,21",
                "485,21Total:",
                "INFORMATIVA",
                "F.G.T.S DO MES 996 1 0,00 159,58 *",
                "159,58Total:",
                "4.184,79LÃ­quido Geral:",
            ],
        )
    ]

    report = parse_dominio_payroll_pages(pages)
    company = report.companies[0]
    sources = {item.signal: tuple(item.rubric_codes) for item in company.signal_sources if item.value}

    assert company.has_employee is True
    assert company.has_pro_labore is True
    assert company.has_inss is True
    assert company.has_fgts is True
    assert sources["has_employee"] == ("1", "996", "998")
    assert "100" not in sources["has_employee"]
    assert "843" not in sources["has_employee"]


def test_parse_emits_structured_warnings_for_invalid_cnpj_and_page_sequence() -> None:
    pages = [
        build_dominio_page(
            page_label="2/2",
            company_code="0008",
            company_name="EMPRESA FICTICIA THETA LTDA",
            cnpj="12.345.678/0001-00",
            competencia="05/2026",
            body_lines=["Folha Mensal", "PROVENTOS", "PRO-LABORE 100 1 220,00 3.483,00", "3.483,00Total:", "3.483,00LÃ­quido Geral:"],
        )
    ]

    report = parse_dominio_payroll_pages(pages)
    company = report.companies[0]
    warning_codes = Counter(warning.code for warning in company.warnings)

    assert warning_codes[DominioPayrollWarningCode.INVALID_CNPJ] == 1
    assert warning_codes[DominioPayrollWarningCode.DECLARED_PAGE_SEQUENCE_MISMATCH] >= 1
    assert company.company_cnpj is None or company.company_cnpj == "12345678000100"
    assert company.confidence == DominioParserConfidence.LOW


def test_parse_reports_multiple_competences_in_same_file() -> None:
    pages = [
        build_dominio_page(
            page_label="1/1",
            company_code="0009",
            company_name="EMPRESA FICTICIA IOTA LTDA",
            cnpj="82.345.678/0001-95",
            competencia="05/2026",
            body_lines=["Folha Mensal", "PROVENTOS", "PRO-LABORE 100 1 220,00 3.483,00", "3.483,00Total:", "3.483,00LÃ­quido Geral:"],
        ),
        build_dominio_page(
            page_label="1/1",
            company_code="0010",
            company_name="EMPRESA FICTICIA KAPPA LTDA",
            cnpj="92.345.678/0001-95",
            competencia="06/2026",
            body_lines=["Folha Mensal", "PROVENTOS", "PRO-LABORE 100 1 220,00 3.483,00", "3.483,00Total:", "3.483,00LÃ­quido Geral:"],
        ),
    ]

    report = parse_dominio_payroll_pages(pages)
    warning_codes = Counter(warning.code for warning in report.warnings)
    assert warning_codes[DominioPayrollWarningCode.MULTIPLE_COMPETENCES_IN_FILE] == 1


def test_parse_rejects_blank_text_layers() -> None:
    with pytest.raises(DominioPayrollTextLayerMissingError):
        parse_dominio_payroll_pages(["   "])


def test_parse_rejects_files_without_any_company_block() -> None:
    pages = ["RESUMO DA FOLHA\nArquivo sintÃ©tico sem empresas\n"]
    with pytest.raises(DominioPayrollNoCompanyBlocksFoundError):
        parse_dominio_payroll_pages(pages)


def test_parse_pdf_boundary_with_synthetic_pdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / "Resumo_Mensal_05-2026.pdf"
    page_text = build_dominio_page(
        page_label="1/1",
        company_code="0011",
        company_name="EMPRESA FICTICIA LAMBDA LTDA",
        cnpj="11.345.678/0001-95",
        competencia="05/2026",
        body_lines=[
            "Folha Mensal",
            "PROVENTOS",
            "HORAS NORMAIS 1 1 220:00 1.670,00",
            "1.670,00Total:",
            "1.670,00LÃ­quido Geral:",
        ],
    )

    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), page_text)
    document.save(pdf_path)
    document.close()

    report = parse_dominio_payroll_pdf(pdf_path)

    assert report.source_file_name == "Resumo_Mensal_05-2026.pdf"
    assert report.physical_page_count == 1
    assert len(report.companies) == 1
