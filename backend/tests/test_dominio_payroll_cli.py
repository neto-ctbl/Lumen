from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
import types

from backend.app.models.organization import Organization
from backend.app.services.integrations.dominio.importer import DominioPayrollImportResult
from backend.scripts import import_dominio_payroll


def test_cli_parser_supports_expected_arguments() -> None:
    parser = import_dominio_payroll.build_parser()

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
    assert args.dry_run is True
    assert args.json is True


def test_cli_prints_safe_json_output(monkeypatch, capsys, db_session) -> None:
    organization = Organization(name="CLI Org", slug="cli-org")
    db_session.add(organization)
    db_session.flush()

    monkeypatch.setattr(import_dominio_payroll, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(import_dominio_payroll, "resolve_target_organization", lambda session, organization_slug: organization)
    monkeypatch.setattr(
        import_dominio_payroll,
        "import_dominio_payroll_file",
        lambda session, organization, file_path, dry_run: DominioPayrollImportResult(
            import_id=10,
            duplicate=False,
            already_processing=False,
            dry_run=dry_run,
            status="MANUAL_REVIEW",
            selection_scope="FACTOR_R",
            source_filter_name="Fator R",
            target_company_count=25,
            target_list_sha256="c" * 64,
            file_sha256="a" * 64,
            physical_page_count=149,
            total_companies=137,
            total_matched=90,
            total_unmatched=47,
            total_invalid_cnpj=0,
            total_missing_cnpj=0,
            total_ambiguous=0,
            total_warnings=8,
            total_errors=0,
            source_competences=["2026-05"],
            assessment_competences=["2026-06"],
        ),
    )

    exit_code = import_dominio_payroll.run_import(
        organization_slug="cli-org",
        file_path="Resumo_Mensal_05-2026.pdf",
        dry_run=True,
        output_json=True,
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "MANUAL_REVIEW"
    payload_text = json.dumps(payload).lower()
    assert "12345678000195" not in payload_text
    assert "empresa" not in payload_text


def test_cli_returns_code_2_for_missing_organization(monkeypatch, capsys, db_session) -> None:
    monkeypatch.setattr(import_dominio_payroll, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(
        import_dominio_payroll,
        "resolve_target_organization",
        lambda session, organization_slug: (_ for _ in ()).throw(ValueError("Organization with slug 'missing' was not found.")),
    )

    exit_code = import_dominio_payroll.run_import(
        organization_slug="missing",
        file_path="missing.pdf",
        dry_run=True,
        output_json=False,
    )

    assert exit_code == 2
    assert "missing" in capsys.readouterr().err


def test_cli_closes_session(monkeypatch) -> None:
    closed = {"value": False}

    class FakeSession:
        def close(self) -> None:
            closed["value"] = True

    monkeypatch.setattr(import_dominio_payroll, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(import_dominio_payroll, "resolve_target_organization", lambda session, organization_slug: object())
    monkeypatch.setattr(
        import_dominio_payroll,
        "import_dominio_payroll_file",
        lambda session, organization, file_path, dry_run: DominioPayrollImportResult(
            import_id=None,
            duplicate=False,
            already_processing=False,
            dry_run=dry_run,
            status="DRY_RUN",
            selection_scope="UNKNOWN",
            source_filter_name=None,
            target_company_count=None,
            target_list_sha256=None,
            file_sha256="b" * 64,
            physical_page_count=1,
            total_companies=1,
            total_matched=0,
            total_unmatched=1,
            total_invalid_cnpj=0,
            total_missing_cnpj=0,
            total_ambiguous=0,
            total_warnings=0,
            total_errors=0,
            source_competences=["2026-05"],
            assessment_competences=["2026-06"],
        ),
    )

    exit_code = import_dominio_payroll.run_import(
        organization_slug="cli-org",
        file_path="Resumo_Mensal_05-2026.pdf",
        dry_run=True,
        output_json=False,
    )

    assert exit_code == 0
    assert closed["value"] is True


def test_collector_load_config_ignores_factor_r_summary_for_ativas(monkeypatch, tmp_path: Path) -> None:
    collector_path = Path("scripts/collectors/dominio/gerar_resumo_mensal_dominio.py").resolve()
    module_name = "collector_test_module"
    spec = importlib.util.spec_from_file_location(module_name, collector_path)
    assert spec is not None
    assert spec.loader is not None

    pywinauto_module = types.ModuleType("pywinauto")
    pywinauto_module.Application = object
    pywinauto_module.Desktop = object
    pywinauto_keyboard_module = types.ModuleType("pywinauto.keyboard")
    pywinauto_keyboard_module.send_keys = lambda *args, **kwargs: None
    dotenv_module = types.ModuleType("dotenv")
    dotenv_module.load_dotenv = lambda *args, **kwargs: False
    pypdf_module = types.ModuleType("pypdf")
    pypdf_module.PdfReader = object
    comtypes_module = types.ModuleType("comtypes")
    comtypes_gen_module = types.ModuleType("comtypes.gen")
    comtypes_module.gen = comtypes_gen_module

    monkeypatch.setitem(sys.modules, "win32clipboard", types.ModuleType("win32clipboard"))
    monkeypatch.setitem(sys.modules, "pywinauto", pywinauto_module)
    monkeypatch.setitem(sys.modules, "pywinauto.keyboard", pywinauto_keyboard_module)
    monkeypatch.setitem(sys.modules, "dotenv", dotenv_module)
    monkeypatch.setitem(sys.modules, "pypdf", pypdf_module)
    monkeypatch.setitem(sys.modules, "comtypes", comtypes_module)
    monkeypatch.setitem(sys.modules, "comtypes.gen", comtypes_gen_module)

    collector = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = collector
    spec.loader.exec_module(collector)

    summary_path = tmp_path / "factor_r_targets.summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "selection_scope": "FACTOR_R",
                "target_company_count": 43,
                "target_list_sha256": "d" * 64,
            }
        ),
        encoding="utf-8",
    )

    repo_root = Path(collector.__file__).resolve().parents[3]
    monkeypatch.setenv("DOMINIO_PASSWORD", "secret")
    monkeypatch.setenv("DOMINIO_TARGETS_SUMMARY_PATH", str(summary_path))
    monkeypatch.setenv("DOMINIO_OUTPUT_DIR", str(tmp_path))
    monkeypatch.delenv("DOMINIO_COMPANY_FILTER", raising=False)
    monkeypatch.chdir(repo_root)

    args = argparse.Namespace(
        competencia="06/2026",
        competencia_de=None,
        competencia_ate=None,
        saida=None,
        company_filter="Ativas",
        nao_sobrescrever=False,
        fechar_dominio=False,
    )

    config = collector.load_config(args)

    assert config.selection_scope == "ACTIVE_COMPANIES"
    assert config.company_filter == "Ativas"
    assert config.targets_summary_path is None
    assert config.target_company_count is None
    assert config.target_list_sha256 is None
