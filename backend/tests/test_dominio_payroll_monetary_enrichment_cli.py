from __future__ import annotations

import json

from backend.app.models.organization import Organization
from backend.app.services.integrations.dominio.enrichment import DominioPayrollMonetaryEnrichmentResult
from backend.scripts import enrich_dominio_payroll_monetary_summary


def test_cli_parser_supports_expected_arguments() -> None:
    parser = enrich_dominio_payroll_monetary_summary.build_parser()

    args = parser.parse_args(
        [
            "--organization-slug",
            "org-a",
            "--file",
            "Resumo_Mensal_05-2026.pdf",
            "--dry-run",
            "--json",
        ]
    )

    assert args.organization_slug == "org-a"
    assert args.file == "Resumo_Mensal_05-2026.pdf"
    assert args.directory is None
    assert args.dry_run is True
    assert args.json is True


def test_cli_prints_safe_json_output(monkeypatch, capsys, db_session) -> None:
    organization = Organization(name="CLI Org", slug="cli-org-enrichment")
    db_session.add(organization)
    db_session.flush()

    monkeypatch.setattr(enrich_dominio_payroll_monetary_summary, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(
        enrich_dominio_payroll_monetary_summary,
        "resolve_target_organization",
        lambda session, organization_slug: organization,
    )
    monkeypatch.setattr(
        enrich_dominio_payroll_monetary_summary,
        "enrich_dominio_payroll_monetary_summary",
        lambda session, organization, file_path, dry_run: DominioPayrollMonetaryEnrichmentResult(
            file_name="Resumo_Mensal_05-2026.pdf",
            file_sha256="a" * 64,
            imports_found=1,
            movements_parsed=137,
            movements_matched=137,
            movements_changed=137,
            schema_v2=137,
            complete=90,
            partial=47,
            insufficient=0,
            unclassified_monetary_movements=47,
            already_enriched=0,
            dry_run=dry_run,
        ),
    )

    exit_code = enrich_dominio_payroll_monetary_summary.run_enrichment(
        organization_slug="cli-org-enrichment",
        file_path="Resumo_Mensal_05-2026.pdf",
        directory_path=None,
        dry_run=True,
        output_json=True,
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["imports_found"] == 1
    assert payload["movements_would_update"] == 137
    assert "Empresa" not in json.dumps(payload)


def test_cli_requires_exactly_one_input_source(capsys) -> None:
    exit_code = enrich_dominio_payroll_monetary_summary.run_enrichment(
        organization_slug="cli-org-enrichment",
        file_path=None,
        directory_path=None,
        dry_run=True,
        output_json=False,
    )

    assert exit_code == 2
    assert "Exactly one" in capsys.readouterr().err
