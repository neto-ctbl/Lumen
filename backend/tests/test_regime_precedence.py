from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from backend.app.models.acessorias_company_snapshot import AcessoriasCompanySnapshot
from backend.app.models.external_company import ExternalCompany
from backend.app.models.fiscal_alert import FiscalAlert
from backend.app.models.fiscal_period import FiscalPeriod
from backend.app.models.organization import Organization
from backend.app.services import lumen_read_model
from backend.app.services.integrations.acessorias.regime import upsert_regime_divergence_alert


def _seed_org_company(db_session, *, raw_econtrole: dict | None = None) -> tuple[Organization, ExternalCompany]:
    organization = Organization(name="Org Regime", slug="org-regime")
    db_session.add(organization)
    db_session.flush()
    company = ExternalCompany(
        organization_id=organization.id,
        cnpj="11111111000111",
        razao_social="Alpha Ltda",
        active=True,
        raw_econtrole=raw_econtrole,
    )
    db_session.add(company)
    db_session.flush()
    db_session.add(
        FiscalPeriod(
            organization_id=organization.id,
            year=2026,
            month=6,
            competencia="2026-06",
            status="OPEN",
        )
    )
    db_session.flush()
    return organization, company


def test_read_model_keeps_placeholder_without_snapshot(db_session) -> None:
    organization, _ = _seed_org_company(db_session)

    companies = lumen_read_model.list_companies(db_session, organization_id=organization.id, search=None)

    assert companies.items[0].regime_label == "Aguardando Acessorias"


def test_read_model_uses_acessorias_snapshot_and_unmapped_label(db_session) -> None:
    organization, company = _seed_org_company(db_session)
    db_session.add(
        AcessoriasCompanySnapshot(
            organization_id=organization.id,
            company_id=company.id,
            external_company_id="9001",
            identifier=company.cnpj,
            razao_social=company.razao_social,
            nome_fantasia=None,
            external_status="Ativa",
            regime_raw="Simples Nacional",
            regime_code=None,
            regime_canonical="SIMPLES_NACIONAL",
            regime_mapping_status="MAPPED",
            raw_payload={},
            retrieved_at=datetime.now(timezone.utc),
        )
    )
    db_session.flush()

    companies = lumen_read_model.list_companies(db_session, organization_id=organization.id, search=None)

    assert companies.items[0].regime_label == "Simples Nacional"

    snapshot = db_session.scalar(select(AcessoriasCompanySnapshot).where(AcessoriasCompanySnapshot.company_id == company.id))
    assert snapshot is not None
    snapshot.regime_canonical = None
    snapshot.regime_mapping_status = "UNMAPPED"
    db_session.flush()

    companies = lumen_read_model.list_companies(db_session, organization_id=organization.id, search=None)
    assert companies.items[0].regime_label == "Regime nao mapeado"


def test_divergence_alert_is_idempotent_and_requires_mappable_econtrole_regime(db_session) -> None:
    organization, company = _seed_org_company(db_session, raw_econtrole={"regime": "Lucro Real"})
    snapshot = AcessoriasCompanySnapshot(
        organization_id=organization.id,
        company_id=company.id,
        external_company_id="9001",
        identifier=company.cnpj,
        razao_social=company.razao_social,
        nome_fantasia=None,
        external_status="Ativa",
        regime_raw="Simples Nacional",
        regime_code=None,
        regime_canonical="SIMPLES_NACIONAL",
        regime_mapping_status="MAPPED",
        raw_payload={},
        retrieved_at=datetime.now(timezone.utc),
    )
    db_session.add(snapshot)
    db_session.flush()

    upsert_regime_divergence_alert(
        db_session,
        organization_id=organization.id,
        company_id=company.id,
        acessorias_snapshot=snapshot,
        econtrole_raw_payload=company.raw_econtrole,
    )
    upsert_regime_divergence_alert(
        db_session,
        organization_id=organization.id,
        company_id=company.id,
        acessorias_snapshot=snapshot,
        econtrole_raw_payload=company.raw_econtrole,
    )

    alerts = db_session.scalars(select(FiscalAlert)).all()
    assert len(alerts) == 1

    company.raw_econtrole = {}
    db_session.flush()
    upsert_regime_divergence_alert(
        db_session,
        organization_id=organization.id,
        company_id=company.id,
        acessorias_snapshot=snapshot,
        econtrole_raw_payload=company.raw_econtrole,
    )
    assert len(db_session.scalars(select(FiscalAlert)).all()) == 1
