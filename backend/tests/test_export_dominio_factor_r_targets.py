from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from backend.app.models.acessorias_company_snapshot import AcessoriasCompanySnapshot
from backend.app.models.company_cnae import CompanyCnae
from backend.app.models.dominio_payroll import DominioPayrollCompanyMovement, DominioPayrollImport
from backend.app.models.econet_cnae_cache import EconetCnaeCache
from backend.app.models.external_company import ExternalCompany
from backend.app.models.fiscal_period import FiscalPeriod
from backend.app.models.organization import Organization
from backend.app.models.sittax_apuracao_snapshot import SittaxApuracaoSnapshot
from backend.app.models.sittax_company_snapshot import SittaxCompanySnapshot
from backend.app.services.integrations.econet.parser import CURRENT_ECONET_PARSER_VERSION
from backend.app.services.integrations.dominio.factor_r_targets import (
    FILTER_ACTION_INCLUDE,
    FILTER_ACTION_MISSING_DOMINIO_CODE,
    FILTER_ACTION_REMOVE,
    FILTER_ACTION_REVIEW,
    build_dominio_factor_r_targets,
)
from backend.app.services.integrations.dominio.selection_scope import selection_scope_from_company_filter
from backend.scripts import export_dominio_factor_r_targets


def _create_org(db_session, slug: str) -> Organization:
    organization = Organization(name=slug, slug=slug)
    db_session.add(organization)
    db_session.flush()
    return organization


def _create_company(db_session, organization: Organization, *, cnpj: str, name: str, active: bool = True) -> ExternalCompany:
    company = ExternalCompany(
        organization_id=organization.id,
        cnpj=cnpj,
        razao_social=name,
        active=active,
    )
    db_session.add(company)
    db_session.flush()
    return company


def _add_snapshot(db_session, organization: Organization, company: ExternalCompany, regime_canonical: str | None, regime_raw: str) -> None:
    db_session.add(
        AcessoriasCompanySnapshot(
            organization_id=organization.id,
            company_id=company.id,
            external_company_id=f"ext-{company.id}",
            identifier=company.cnpj,
            razao_social=company.razao_social,
            nome_fantasia=None,
            external_status="ATIVA",
            regime_raw=regime_raw,
            regime_code=None,
            regime_canonical=regime_canonical,
            regime_mapping_status="MAPPED" if regime_canonical else "UNMAPPED",
            raw_payload={},
            retrieved_at=datetime.now(timezone.utc),
        )
    )


def _add_cnae(db_session, company: ExternalCompany, *, cnae: str, active: bool = True, is_primary: bool = True) -> None:
    db_session.add(
        CompanyCnae(
            company_id=company.id,
            cnae=cnae,
            cnae_formatted=f"{cnae[:4]}-{cnae[4:]}" if len(cnae) == 7 else cnae,
            is_primary=is_primary,
            source="ECONTROLE",
            active=active,
            first_seen_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
            deactivated_at=None,
        )
    )


def _add_econet_cache(db_session, *, cnae: str, factor_r_applicable: bool | None) -> None:
    db_session.add(
        EconetCnaeCache(
            cnae=cnae,
            cnae_formatted=f"{cnae[:4]}-{cnae[4:]}",
            description="CNAE sintetico",
            econet_id_cnae=f"id-{cnae}",
            activity_types=["SERVICOS"],
            simples_status="ALLOWED",
            simples_allowed=True,
            simples_annex_default="V",
            simples_annex_conditional="III",
            factor_r_applicable=factor_r_applicable,
            factor_r_threshold=Decimal("28.00") if factor_r_applicable else None,
            mei_status="NOT_ALLOWED",
            mei_allowed=False,
            mei_occupation=None,
            presumed_profit_status="ALLOWED",
            presumed_profit_allowed=True,
            presumed_profit_irpj_rate=None,
            presumed_profit_csll_rate=None,
            actual_profit_status="ALLOWED",
            actual_profit_mandatory=False,
            obligations_general={},
            obligations_simples={},
            obligations_simei={},
            unmapped_obligations=[],
            normalized_payload={},
            parse_status="PARSED",
            parser_version=CURRENT_ECONET_PARSER_VERSION,
            content_hash="a" * 64,
            retrieved_at=datetime.now(timezone.utc),
            expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        )
    )


def _add_dominio_code(db_session, organization: Organization, company: ExternalCompany, *, code: str) -> None:
    payroll_import = DominioPayrollImport(
        organization_id=organization.id,
        assessment_period_id=None,
        source="DOMINIO_FOLHA_RESUMO",
        evidence_source="DOMINIO_FOLHA_PDF",
        parser_version="test",
        status="COMPLETED",
        selection_scope="FACTOR_R",
        source_filter_name="Fator R",
        target_company_count=1,
        target_list_sha256="b" * 64,
        source_file_name="Resumo_Mensal_05-2026.pdf",
        source_file_path=None,
        file_sha256=("f" * 63) + str(company.id % 10),
        file_size_bytes=100,
        physical_page_count=1,
        source_competences=["2026-05"],
        assessment_competences=["2026-06"],
        started_at=datetime.now(timezone.utc),
        processed_at=datetime.now(timezone.utc),
        imported_at=datetime.now(timezone.utc),
        warnings=[],
        errors=[],
        raw_metadata={},
    )
    db_session.add(payroll_import)
    db_session.flush()
    db_session.add(
        DominioPayrollCompanyMovement(
            import_id=payroll_import.id,
            organization_id=organization.id,
            external_company_id=company.id,
            fiscal_period_id=None,
            source_company_key=f"{code}|{company.cnpj}|2026-05",
            dominio_company_code=code,
            company_cnpj=company.cnpj,
            source_company_name=company.razao_social,
            source_payroll_competence=datetime(2026, 5, 1).date(),
            assessment_competence=datetime(2026, 6, 1).date(),
            match_status="MATCHED",
            parser_confidence="HIGH",
            calculation_type="Folha",
            has_payroll=True,
            has_employee=True,
            has_pro_labore=False,
            has_autonomous=False,
            has_inss=True,
            has_fgts=True,
            has_termination=False,
            has_vacation=False,
            has_leave=False,
            gross_total=Decimal("1.00"),
            discount_total=Decimal("0.00"),
            informative_total=Decimal("0.00"),
            net_total=Decimal("1.00"),
            source_page_start=1,
            source_page_end=1,
            source_page_count=1,
            source_page_numbers=[1],
            declared_page_count=1,
            movement_hash=("e" * 63) + str(company.id % 10),
            rubrics_summary={},
            warnings=[],
            raw_text="safe",
        )
    )


def _add_sittax_effective_use(db_session, organization: Organization, company: ExternalCompany, *, factor_r_percent: Decimal | None) -> None:
    company_snapshot = SittaxCompanySnapshot(
        organization_id=organization.id,
        company_id=company.id,
        sittax_company_id=f"sittax-{company.id}",
        cnpj="".join(ch for ch in company.cnpj if ch.isdigit()),
        legal_name=company.razao_social,
        trade_name=None,
        state_registration=None,
        state=None,
        status="ATIVA",
        homologated=True,
        cash_regime=False,
        match_status="MATCHED",
        raw_payload={},
        first_seen_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
    )
    db_session.add(company_snapshot)
    period = FiscalPeriod(
        organization_id=organization.id,
        year=2026,
        month=6,
        competencia="2026-06",
        status="OPEN",
    )
    db_session.add(period)
    db_session.flush()
    db_session.add(
        SittaxApuracaoSnapshot(
            organization_id=organization.id,
            sittax_company_snapshot_id=company_snapshot.id,
            external_company_id=company.id,
            fiscal_period_id=period.id,
            sittax_apuracao_id=f"apur-{company.id}",
            company_cnpj="".join(ch for ch in company.cnpj if ch.isdigit()),
            company_name=company.razao_social,
            period_reference="2026-06",
            is_transmitted=True,
            transmission_in_progress=False,
            transmission_type="TEST",
            transmitted_at=datetime.now(timezone.utc),
            net_revenue=Decimal("1000.00"),
            product_revenue=Decimal("0.00"),
            service_revenue=Decimal("1000.00"),
            return_revenue=Decimal("0.00"),
            rbt12=Decimal("12000.00"),
            rba=Decimal("1000.00"),
            das_amount=Decimal("60.00"),
            das_xml_amount=Decimal("60.00"),
            factor_r_percent=factor_r_percent,
            company_has_payroll=True,
            taxes_icms=False,
            taxes_iss=True,
            taxes_ipi=False,
            taxes_pis_cofins=False,
            companies_apuracao=[],
            annexes=[],
            cfops=[],
            activities=[],
            payrolls=[],
            alerts=[],
            errors=[],
            risks=[],
            raw_payload={},
            first_seen_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
    )


def test_build_targets_covers_include_remove_review_missing_code_and_org_isolation(db_session) -> None:
    organization = _create_org(db_session, "org-factor-r")
    other_org = _create_org(db_session, "org-factor-r-other")

    include_company = _create_company(db_session, organization, cnpj="11.111.111/0001-11", name="Beta Ltda")
    mei_company = _create_company(db_session, organization, cnpj="22.222.222/0001-22", name="Mei Ltda")
    lucro_company = _create_company(db_session, organization, cnpj="33.333.333/0001-33", name="Lucro Ltda")
    inactive_company = _create_company(db_session, organization, cnpj="44.444.444/0001-44", name="Inativa Ltda", active=False)
    review_company = _create_company(db_session, organization, cnpj="55.555.555/0001-55", name="Review Ltda")
    missing_code_company = _create_company(db_session, organization, cnpj="66.666.666/0001-66", name="Sem Codigo Ltda")
    other_company = _create_company(db_session, other_org, cnpj="77.777.777/0001-77", name="Outra Org Ltda")

    _add_snapshot(db_session, organization, include_company, "SIMPLES_NACIONAL", "Simples Nacional")
    _add_snapshot(db_session, organization, mei_company, "MEI", "MEI")
    _add_snapshot(db_session, organization, lucro_company, "LUCRO_REAL", "Lucro Real")
    _add_snapshot(db_session, organization, inactive_company, "SIMPLES_NACIONAL", "Simples Nacional")
    _add_snapshot(db_session, organization, missing_code_company, "SIMPLES_NACIONAL", "Simples Nacional")
    _add_snapshot(db_session, other_org, other_company, "SIMPLES_NACIONAL", "Simples Nacional")

    _add_cnae(db_session, include_company, cnae="7020400")
    _add_cnae(db_session, mei_company, cnae="7020400")
    _add_cnae(db_session, lucro_company, cnae="7020400")
    _add_cnae(db_session, inactive_company, cnae="7020400")
    _add_cnae(db_session, review_company, cnae="7020400")
    _add_cnae(db_session, missing_code_company, cnae="7020400")
    _add_cnae(db_session, other_company, cnae="7020400")

    _add_econet_cache(db_session, cnae="7020400", factor_r_applicable=True)
    _add_dominio_code(db_session, organization, include_company, code="0002")
    _add_dominio_code(db_session, other_org, other_company, code="9999")
    _add_sittax_effective_use(db_session, organization, include_company, factor_r_percent=Decimal("30.00"))
    db_session.flush()

    export = build_dominio_factor_r_targets(db_session, organization=organization)
    rows_by_name = {row.company_name: row for row in export.rows}

    assert rows_by_name["Beta Ltda"].filter_action == FILTER_ACTION_INCLUDE
    assert rows_by_name["Beta Ltda"].factor_r_effectively_used is True
    assert rows_by_name["Mei Ltda"].filter_action == FILTER_ACTION_REMOVE
    assert rows_by_name["Lucro Ltda"].filter_action == FILTER_ACTION_REMOVE
    assert rows_by_name["Inativa Ltda"].filter_action == FILTER_ACTION_REMOVE
    assert rows_by_name["Review Ltda"].filter_action == FILTER_ACTION_REVIEW
    assert rows_by_name["Sem Codigo Ltda"].filter_action == FILTER_ACTION_MISSING_DOMINIO_CODE
    assert "Outra Org Ltda" not in rows_by_name


def test_manual_dominio_code_fallback_promotes_company_to_include(db_session) -> None:
    organization = _create_org(db_session, "neto-contabilidade")
    company = _create_company(db_session, organization, cnpj="24.415.962/0001-70", name="Fallback Manual Ltda")
    _add_snapshot(db_session, organization, company, "SIMPLES_NACIONAL", "Simples Nacional")
    _add_cnae(db_session, company, cnae="7020400")
    _add_econet_cache(db_session, cnae="7020400", factor_r_applicable=True)
    db_session.flush()

    export = build_dominio_factor_r_targets(db_session, organization=organization)
    row = next(row for row in export.rows if row.company_cnpj == "24.415.962/0001-70")

    assert row.dominio_company_code == "230"
    assert row.filter_action == FILTER_ACTION_INCLUDE


def test_imported_dominio_code_has_precedence_over_manual_fallback(db_session) -> None:
    organization = _create_org(db_session, "neto-contabilidade")
    company = _create_company(db_session, organization, cnpj="24.415.962/0001-70", name="Preferir Importacao Ltda")
    _add_snapshot(db_session, organization, company, "SIMPLES_NACIONAL", "Simples Nacional")
    _add_cnae(db_session, company, cnae="7020400")
    _add_econet_cache(db_session, cnae="7020400", factor_r_applicable=True)
    _add_dominio_code(db_session, organization, company, code="9998")
    db_session.flush()

    export = build_dominio_factor_r_targets(db_session, organization=organization)
    row = next(row for row in export.rows if row.company_cnpj == "24.415.962/0001-70")

    assert row.dominio_company_code == "9998"
    assert row.filter_action == FILTER_ACTION_INCLUDE


def test_manual_dominio_code_fallback_isolated_by_organization(db_session) -> None:
    organization = _create_org(db_session, "org-without-manual-fallback")
    company = _create_company(db_session, organization, cnpj="24.415.962/0001-70", name="Sem Fallback Ltda")
    _add_snapshot(db_session, organization, company, "SIMPLES_NACIONAL", "Simples Nacional")
    _add_cnae(db_session, company, cnae="7020400")
    _add_econet_cache(db_session, cnae="7020400", factor_r_applicable=True)
    db_session.flush()

    export = build_dominio_factor_r_targets(db_session, organization=organization)
    row = next(row for row in export.rows if row.company_cnpj == "24.415.962/0001-70")

    assert row.dominio_company_code is None
    assert row.filter_action == FILTER_ACTION_MISSING_DOMINIO_CODE


def test_target_hash_is_stable_and_changes_when_include_list_changes(db_session) -> None:
    organization = _create_org(db_session, "org-factor-r-hash")
    first = _create_company(db_session, organization, cnpj="10.000.000/0001-00", name="Alpha")
    second = _create_company(db_session, organization, cnpj="20.000.000/0001-00", name="Zulu")
    for company, code in ((first, "0001"), (second, "0002")):
        _add_snapshot(db_session, organization, company, "SIMPLES_NACIONAL", "Simples Nacional")
        _add_cnae(db_session, company, cnae="7020400")
        _add_dominio_code(db_session, organization, company, code=code)
    _add_econet_cache(db_session, cnae="7020400", factor_r_applicable=True)
    db_session.flush()

    first_export = build_dominio_factor_r_targets(db_session, organization=organization)
    second_export = build_dominio_factor_r_targets(db_session, organization=organization)
    assert first_export.target_list_sha256 == second_export.target_list_sha256

    third = _create_company(db_session, organization, cnpj="30.000.000/0001-00", name="Bravo")
    _add_snapshot(db_session, organization, third, "SIMPLES_NACIONAL", "Simples Nacional")
    _add_cnae(db_session, third, cnae="7020400")
    _add_dominio_code(db_session, organization, third, code="0003")
    db_session.flush()

    changed_export = build_dominio_factor_r_targets(db_session, organization=organization)
    assert changed_export.target_list_sha256 != first_export.target_list_sha256


def test_export_script_writes_sorted_csv_and_safe_summary(monkeypatch, capsys, db_session, tmp_path: Path) -> None:
    organization = _create_org(db_session, "org-factor-r-script")
    first = _create_company(db_session, organization, cnpj="12.000.000/0001-00", name="Zulu")
    second = _create_company(db_session, organization, cnpj="11.000.000/0001-00", name="Alpha")
    for company, code in ((first, "0002"), (second, "0001")):
        _add_snapshot(db_session, organization, company, "SIMPLES_NACIONAL", "Simples Nacional")
        _add_cnae(db_session, company, cnae="7020400")
        _add_dominio_code(db_session, organization, company, code=code)
    _add_econet_cache(db_session, cnae="7020400", factor_r_applicable=True)
    db_session.flush()

    monkeypatch.setattr(export_dominio_factor_r_targets, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(
        export_dominio_factor_r_targets,
        "resolve_target_organization",
        lambda session, organization_slug: organization,
    )

    csv_path = tmp_path / "factor_r.csv"
    summary_path = tmp_path / "factor_r.summary.json"
    exit_code = export_dominio_factor_r_targets.run_export(
        organization_slug=organization.slug,
        output_path=str(csv_path),
        json_summary_path=str(summary_path),
    )

    assert exit_code == 0
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["dominio_company_code"] for row in rows] == ["0001", "0002"]

    summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary_payload["selection_scope"] == "FACTOR_R"
    assert "Alpha" not in json.dumps(summary_payload)
    assert "11.000.000/0001-00" not in json.dumps(summary_payload)

    terminal_summary = json.loads(capsys.readouterr().out.strip())
    assert terminal_summary["target_company_count"] == 2
    assert "Alpha" not in json.dumps(terminal_summary)
    assert "11.000.000/0001-00" not in json.dumps(terminal_summary)


def test_parser_and_gitignore_cover_new_operational_scope() -> None:
    parser = export_dominio_factor_r_targets.build_parser()
    args = parser.parse_args(
        [
            "--organization-slug",
            "org",
            "--output",
            "scripts/collectors/dominio/inputs/factor_r.csv",
            "--json-summary",
            "scripts/collectors/dominio/inputs/factor_r.summary.json",
        ]
    )
    assert args.organization_slug == "org"
    assert selection_scope_from_company_filter("Fator R") == "FACTOR_R"
    assert selection_scope_from_company_filter("Ativas") == "ACTIVE_COMPANIES"

    gitignore = Path(".gitignore").read_text(encoding="utf-8")
    assert "scripts/collectors/dominio/inputs/" in gitignore
