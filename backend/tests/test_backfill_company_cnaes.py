from __future__ import annotations

import subprocess
import sys

from backend.app.models.external_company import ExternalCompany
from backend.app.models.organization import Organization
from backend.app.services.integrations.econtrole.sync import upsert_company_from_econtrole_payload
from backend.scripts.backfill_company_cnaes import run_backfill


def _org(db_session, slug: str) -> Organization:
    organization = Organization(name=slug, slug=slug)
    db_session.add(organization)
    db_session.flush()
    return organization


def _payload(cnpj: str, **overrides):
    payload = {
        "id": cnpj,
        "cnpj": cnpj,
        "razao_social": f"Empresa {cnpj}",
        "cnae_principal": "8630-5/03",
        "cnaes_secundarios": ["8650-0/01"],
    }
    payload.update(overrides)
    return payload


def test_backfill_company_cnaes_dry_run(db_session) -> None:
    org = _org(db_session, "org-backfill-dry")
    upsert_company_from_econtrole_payload(db_session, organization=org, payload=_payload("19163109000178"))
    db_session.rollback()
    org = _org(db_session, "org-backfill-dry-real")
    company = ExternalCompany(organization_id=org.id, cnpj="19163109000178", razao_social="Empresa", cnae_principal="8630-5/03", cnaes_secundarios=["8650-0/01"], active=True)
    db_session.add(company)
    db_session.flush()
    summary = run_backfill(db_session, org_slug=org.slug, dry_run=True)
    assert summary["created"] == 2


def test_backfill_company_cnaes_is_idempotent(db_session) -> None:
    org = _org(db_session, "org-backfill-idem")
    company = ExternalCompany(organization_id=org.id, cnpj="19163109000178", razao_social="Empresa", cnae_principal="8630-5/03", cnaes_secundarios=["8650-0/01"], active=True)
    db_session.add(company)
    db_session.flush()
    first = run_backfill(db_session, org_slug=org.slug)
    second = run_backfill(db_session, org_slug=org.slug)
    assert first["created"] == 2
    assert second["created"] == 0
    assert second["unchanged"] == 2


def test_backfill_script_imports_when_called_by_path() -> None:
    result = subprocess.run(
        [sys.executable, "backend/scripts/backfill_company_cnaes.py", "--help"],
        capture_output=True,
        text=True,
        cwd=".",
    )
    assert result.returncode == 0
