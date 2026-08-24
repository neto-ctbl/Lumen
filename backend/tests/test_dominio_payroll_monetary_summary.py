from __future__ import annotations

from collections import Counter
from decimal import Decimal

from backend.app.services.integrations.dominio.contracts import DominioPayrollWarningCode
from backend.app.services.integrations.dominio.importer import _build_rubrics_summary
from backend.app.services.integrations.dominio.parser import parse_dominio_payroll_pages
from backend.tests.dominio_test_utils import build_dominio_page


def test_monetary_summary_schema_v2_separates_categories_and_preserves_unclassified() -> None:
    pages = [
        build_dominio_page(
            page_label="1/1",
            company_code="0201",
            company_name="EMPRESA FICTICIA MONETARIA LTDA",
            cnpj="12.345.678/0001-95",
            competencia="05/2026",
            body_lines=[
                "Folha Mensal",
                "PROVENTOS",
                "HORAS NORMAIS 1 1 220:00 1.234,56",
                "PRO-LABORE 100 1 220:00 2.000,00",
                "AUTONOMO 235 1 1,00 500,00",
                "13 SALARIO 13 1 1,00 300,00",
                "RUBRICA DESCONHECIDA 7000 1 1,00 500,00",
                "4.534,56Total:",
                "DESCONTOS",
                "INSS EMPREGADOR 843 1 11,00 220,00",
                "I.N.S.S. 998 1 7,78 111,11",
                "331,11Total:",
                "INFORMATIVA",
                "F.G.T.S DO MES 996 1 0,00 99,99 *",
                "99,99Total:",
                "4.203,45Liquido Geral:",
            ],
        )
    ]

    report = parse_dominio_payroll_pages(pages)
    company = report.companies[0]
    summary, warnings = _build_rubrics_summary(company)
    monetary_categories = summary["monetary_categories"]
    warning_codes = Counter(warning.code for warning in warnings)

    assert summary["schema_version"] == 2
    assert summary["monetary_summary_confidence"] == "PARTIAL"
    assert monetary_categories["employee_remuneration"]["amount"] == "1234.56"
    assert monetary_categories["pro_labore"]["amount"] == "2000.00"
    assert monetary_categories["autonomous"]["amount"] == "500.00"
    assert monetary_categories["thirteenth_salary"]["amount"] == "300.00"
    assert monetary_categories["employer_cpp_observed"]["amount"] == "220.00"
    assert monetary_categories["fgts_observed"]["amount"] == "99.99"
    assert summary["unclassified_monetary"]["amount"] == "500.00"
    assert summary["unclassified_monetary"]["rubric_count"] == 1
    assert summary["excluded_monetary"]["amount"] == "111.11"
    assert warning_codes[DominioPayrollWarningCode.UNCLASSIFIED_MONETARY_RUBRICS] == 1


def test_monetary_summary_preserves_decimal_serialization_exactly() -> None:
    pages = [
        build_dominio_page(
            page_label="1/1",
            company_code="0202",
            company_name="EMPRESA FICTICIA DECIMAL LTDA",
            cnpj="22.345.678/0001-95",
            competencia="05/2026",
            body_lines=[
                "Folha Mensal",
                "PROVENTOS",
                "HORAS NORMAIS 1 1 220:00 1.234,56",
                "1.234,56Total:",
                "1.234,56Liquido Geral:",
            ],
        )
    ]

    report = parse_dominio_payroll_pages(pages)
    company = report.companies[0]
    first_rubric = company.rubrics[0]
    summary, _warnings = _build_rubrics_summary(company)

    assert first_rubric.calculated_value == Decimal("1234.56")
    assert summary["monetary_categories"]["employee_remuneration"]["amount"] == "1234.56"


def test_monetary_summary_does_not_fill_gap_from_gross_total() -> None:
    pages = [
        build_dominio_page(
            page_label="1/1",
            company_code="0203",
            company_name="EMPRESA FICTICIA GROSS TOTAL LTDA",
            cnpj="32.345.678/0001-95",
            competencia="05/2026",
            body_lines=[
                "Folha Mensal",
                "PROVENTOS",
                "HORAS NORMAIS 1 1 220:00 1.234,56",
                "RUBRICA DESCONHECIDA 7000 1 1,00 500,00",
                "1.734,56Total:",
                "1.734,56Liquido Geral:",
            ],
        )
    ]

    report = parse_dominio_payroll_pages(pages)
    company = report.companies[0]
    summary, _warnings = _build_rubrics_summary(company)

    assert company.gross_total == Decimal("1734.56")
    assert summary["monetary_categories"]["employee_remuneration"]["amount"] == "1234.56"
    assert summary["unclassified_monetary"]["amount"] == "500.00"
    assert summary["monetary_categories"]["employee_remuneration"]["amount"] != "1734.56"
