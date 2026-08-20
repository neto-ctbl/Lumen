from __future__ import annotations

import subprocess
import sys

from sqlalchemy import select

from backend.app.models.company_activity_type import CompanyActivityType
from backend.app.models.external_company import ExternalCompany
from backend.app.models.organization import Organization
from backend.scripts.backfill_econtrole_companies import run_backfill


def _org(db_session, slug: str) -> Organization:
    organization = Organization(name=slug, slug=slug)
    db_session.add(organization)
    db_session.flush()
    return organization


def _company(db_session, org: Organization, *, cnpj: str, cnae_principal: str = "4711-3/02", active: bool = True, econtrole_company_id: str | None = None) -> ExternalCompany:
    company = ExternalCompany(
        organization_id=org.id,
        cnpj=cnpj,
        razao_social=f"Empresa {cnpj}",
        cnae_principal=cnae_principal,
        cnaes_secundarios=None,
        active=active,
        econtrole_company_id=econtrole_company_id,
    )
    db_session.add(company)
    db_session.flush()
    return company


def test_backfill_econtrole_companies_local_completion_creates_activity_types(db_session, monkeypatch) -> None:
    org = _org(db_session, "org-backfill-econtrole-local")
    company = _company(db_session, org, cnpj="19163109000178")

    monkeypatch.setattr(
        "backend.app.services.integrations.econtrole.webhook_completion._sync_company_regime_from_acessorias",
        lambda session, organization, company: ("SKIPPED_NOT_CONFIGURED", False),
    )
    monkeypatch.setattr(
        "backend.app.services.integrations.econtrole.webhook_completion._enrich_missing_company_cnaes_from_econet",
        lambda session, organization, company: ("SKIPPED_NOT_CONFIGURED", 0),
    )

    summary = run_backfill(
        db_session,
        org_slug=org.slug,
        skip_econtrole_sync=True,
    )

    rows = db_session.scalars(select(CompanyActivityType).where(CompanyActivityType.company_id == company.id)).all()
    assert summary["completion_received"] == 1
    assert summary["completion_processed"] == 1
    assert summary["activity_types_created"] == 1
    assert [row.activity_type for row in rows] == ["COMERCIO"]


def test_backfill_econtrole_companies_syncs_from_econtrole_and_marks_missing_inactive(db_session, monkeypatch) -> None:
    org = _org(db_session, "org-backfill-econtrole-sync")
    kept = _company(db_session, org, cnpj="19163109000178", econtrole_company_id="123")
    missing = _company(db_session, org, cnpj="00999999000199", econtrole_company_id="999")

    payloads = [
        {
            "id": "123",
            "profile_id": "456",
            "cnpj": "19.163.109/0001-78",
            "razao_social": "Empresa 1",
            "situacao": "ATIVA",
            "cnae_principal": "4711-3/02",
        }
    ]

    class _FakeClient:
        def list_companies(self):
            return payloads

    monkeypatch.setattr(
        "backend.scripts.backfill_econtrole_companies.EControleClient.from_settings",
        lambda settings: _FakeClient(),
    )
    monkeypatch.setattr(
        "backend.app.services.integrations.econtrole.webhook_completion._sync_company_regime_from_acessorias",
        lambda session, organization, company: ("SKIPPED_NOT_CONFIGURED", False),
    )
    monkeypatch.setattr(
        "backend.app.services.integrations.econtrole.webhook_completion._enrich_missing_company_cnaes_from_econet",
        lambda session, organization, company: ("SKIPPED_NOT_CONFIGURED", 0),
    )

    summary = run_backfill(
        db_session,
        org_slug=org.slug,
        mark_missing_inactive=True,
        skip_local_completion=True,
    )

    kept = db_session.scalar(select(ExternalCompany).where(ExternalCompany.id == kept.id))
    missing = db_session.scalar(select(ExternalCompany).where(ExternalCompany.id == missing.id))
    assert summary["econtrole_received"] == 1
    assert summary["econtrole_processed"] == 1
    assert summary["missing_marked_inactive"] == 1
    assert kept is not None and kept.active is True
    assert missing is not None and missing.active is False


def test_backfill_econtrole_companies_dry_run_rolls_back(db_session, monkeypatch) -> None:
    org = _org(db_session, "org-backfill-econtrole-dry")
    company = _company(db_session, org, cnpj="19163109000178")

    monkeypatch.setattr(
        "backend.app.services.integrations.econtrole.webhook_completion._sync_company_regime_from_acessorias",
        lambda session, organization, company: ("SKIPPED_NOT_CONFIGURED", False),
    )
    monkeypatch.setattr(
        "backend.app.services.integrations.econtrole.webhook_completion._enrich_missing_company_cnaes_from_econet",
        lambda session, organization, company: ("SKIPPED_NOT_CONFIGURED", 0),
    )

    summary = run_backfill(
        db_session,
        org_slug=org.slug,
        skip_econtrole_sync=True,
        dry_run=True,
    )

    rows = db_session.scalars(select(CompanyActivityType).where(CompanyActivityType.company_id == company.id)).all()
    assert summary["activity_types_created"] == 1
    assert rows == []


def test_backfill_econtrole_companies_help() -> None:
    result = subprocess.run(
        [sys.executable, "backend/scripts/backfill_econtrole_companies.py", "--help"],
        capture_output=True,
        text=True,
        cwd=".",
    )
    assert result.returncode == 0
