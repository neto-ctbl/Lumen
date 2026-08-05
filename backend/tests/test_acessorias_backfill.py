from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from backend.app.models.acessorias_company_snapshot import AcessoriasCompanySnapshot
from backend.app.models.acessorias_delivery_snapshot import AcessoriasDeliverySnapshot
from backend.app.models.external_company import ExternalCompany
from backend.app.models.fiscal_obligation import FiscalObligation
from backend.app.models.fiscal_obligation_status import FiscalObligationStatus
from backend.app.models.fiscal_period import FiscalPeriod
from backend.app.models.integration_sync_run import IntegrationSyncRun
from backend.app.models.organization import Organization
from backend.app.services.integrations.acessorias.backfill import backfill_acessorias, iter_period_range
from backend.app.services.integrations.acessorias.sync import FixtureAcessoriasClient


def _seed_org_company_periods(db_session, *, active: bool = True) -> tuple[Organization, ExternalCompany]:
    organization = Organization(name="Org Backfill", slug="org-backfill")
    db_session.add(organization)
    db_session.flush()

    company = ExternalCompany(
        organization_id=organization.id,
        cnpj="11111111000111",
        razao_social="Alpha Ltda",
        nome_fantasia="Alpha",
        active=active,
        raw_econtrole={"regime": "Lucro Real"},
    )
    db_session.add(company)
    db_session.flush()

    for year, month in ((2025, 12), (2026, 1), (2026, 2), (2026, 6)):
        db_session.add(
            FiscalPeriod(
                organization_id=organization.id,
                year=year,
                month=month,
                competencia=f"{year:04d}-{month:02d}",
                status="OPEN",
            )
        )

    db_session.add_all(
        [
            FiscalObligation(code="DAS", name="DAS", category="SIMPLES", department_default="FISCAL", source_priority=[]),
            FiscalObligation(code="DEFIS", name="DEFIS", category="SIMPLES", department_default="FISCAL", source_priority=[]),
        ]
    )
    db_session.flush()
    return organization, company


def _deliveries_for(period: str, *, base_id: int) -> list[dict]:
    delivery_day = min(18, 28)
    return [
        {
            "ID": "9001",
            "Identificador": "11.111.111/0001-11",
            "Razao": "Alpha Ltda",
            "Fantasia": "Alpha",
            "Entregas": [
                {
                    "Nome": "DAS",
                    "EntCompetencia": f"{period}-01",
                    "EntDtPrazo": f"{period}-{20:02d}",
                    "EntDtAtraso": f"{period}-{21:02d}",
                    "EntDtEntrega": f"{period}-{delivery_day:02d}",
                    "EntDtFinalizacao": f"{period}-{delivery_day:02d} 10:30:00",
                    "EntMulta": "N",
                    "Status": "Ent. antecipada",
                    "EntGuiaLida": "S",
                    "EntLastDH": f"{period}-{delivery_day:02d} 10:30:00",
                    "RespEntrega": "Maria Fiscal",
                    "Config": {
                        "EntID": str(base_id),
                        "Tipo": "O",
                        "ID": "100",
                        "DptoID": "2",
                        "DptoNome": "Fiscal",
                        "CriadorID": None,
                        "RespPrazo": "Joana Prazo",
                        "RespPrazoID": "42",
                        "RespEntrega": "Maria Fiscal",
                        "RespEntregaID": "43",
                    },
                },
                {
                    "Nome": "GPS",
                    "EntCompetencia": f"{period}-01",
                    "EntDtPrazo": f"{period}-{25:02d}",
                    "EntDtAtraso": f"{period}-{26:02d}",
                    "EntDtEntrega": "0000-00-00",
                    "EntDtFinalizacao": None,
                    "EntMulta": "S",
                    "Status": "Atrasada!",
                    "EntGuiaLida": "",
                    "EntLastDH": f"{period}-{25:02d} 12:00:00",
                    "RespEntrega": None,
                    "Config": {
                        "EntID": str(base_id + 1),
                        "Tipo": "O",
                        "ID": "101",
                        "DptoID": "2",
                        "DptoNome": "Fiscal",
                        "CriadorID": None,
                        "RespPrazo": "Joana Prazo",
                        "RespPrazoID": "42",
                        "RespEntrega": None,
                        "RespEntregaID": None,
                    },
                },
                {
                    "Nome": "Consulta do e-Social!",
                    "EntCompetencia": f"{period}-01",
                    "EntDtPrazo": f"{period}-{22:02d}",
                    "EntDtAtraso": f"{period}-{23:02d}",
                    "EntDtEntrega": "0000-00-00",
                    "EntDtFinalizacao": None,
                    "EntMulta": "N",
                    "Status": "Pendente",
                    "EntGuiaLida": "",
                    "EntLastDH": f"{period}-{22:02d} 08:00:00",
                    "RespEntrega": None,
                    "Config": {
                        "EntID": str(base_id + 2),
                        "Tipo": "T",
                        "ID": "102",
                        "DptoID": "1",
                        "DptoNome": "Pessoal",
                        "CriadorID": None,
                        "RespPrazo": "Pessoa DP",
                        "RespPrazoID": "55",
                        "RespEntrega": None,
                        "RespEntregaID": None,
                    },
                },
            ],
        }
    ]


def _fixture_client() -> FixtureAcessoriasClient:
    return FixtureAcessoriasClient(
        companies=[
            {
                "ID": "9001",
                "Identificador": "11.111.111/0001-11",
                "Razao": "Alpha Ltda",
                "Fantasia": "Alpha",
                "Status": "Ativa",
                "UF": "GO",
                "Regime": "Simples Nacional",
            },
            {
                "ID": "9002",
                "Identificador": "22.222.222/0001-22",
                "Razao": "Empresa Sem Match Ltda",
                "Fantasia": "Sem Match",
                "Status": "Ativa",
                "UF": "GO",
                "Regime": "7",
            },
        ],
        deliveries_by_period={
            "2025-12": _deliveries_for("2025-12", base_id=5100),
            "2026-01": _deliveries_for("2026-01", base_id=5200),
            "2026-02": _deliveries_for("2026-02", base_id=5300),
            "2026-06": _deliveries_for("2026-06", base_id=5600),
        },
    )


def test_iter_period_range_supports_single_multiple_and_year_rollover() -> None:
    assert iter_period_range("2026-06", "2026-06") == ["2026-06"]
    assert iter_period_range("2025-12", "2026-02") == ["2025-12", "2026-01", "2026-02"]


def test_iter_period_range_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="YYYY-MM"):
        iter_period_range("06/2026", "2026-06")
    with pytest.raises(ValueError, match="valid month"):
        iter_period_range("2026-13", "2026-13")
    with pytest.raises(ValueError, match="from-period"):
        iter_period_range("2026-07", "2026-06")


def test_backfill_requires_existing_periods_before_api_calls(db_session) -> None:
    organization, _ = _seed_org_company_periods(db_session)

    with pytest.raises(ValueError, match="2026-03"):
        backfill_acessorias(
            db_session,
            organization=organization,
            from_period="2026-02",
            to_period="2026-03",
            client=_fixture_client(),
        )


def test_backfill_syncs_companies_once_and_processes_multiple_periods_idempotently(db_session, monkeypatch) -> None:
    organization, company = _seed_org_company_periods(db_session)
    client = _fixture_client()
    company_calls = {"count": 0}

    import backend.app.services.integrations.acessorias.backfill as backfill_module

    original_sync = backfill_module.sync_acessorias_companies

    def counting_sync(*args, **kwargs):
        company_calls["count"] += 1
        return original_sync(*args, **kwargs)

    monkeypatch.setattr(backfill_module, "sync_acessorias_companies", counting_sync)

    first = backfill_acessorias(
        db_session,
        organization=organization,
        from_period="2025-12",
        to_period="2026-02",
        client=client,
    )
    second = backfill_acessorias(
        db_session,
        organization=organization,
        from_period="2025-12",
        to_period="2026-02",
        client=client,
    )

    company_snapshots = db_session.scalars(select(AcessoriasCompanySnapshot)).all()
    delivery_snapshots = db_session.scalars(select(AcessoriasDeliverySnapshot)).all()
    statuses = db_session.scalars(select(FiscalObligationStatus)).all()
    runs = db_session.scalars(select(IntegrationSyncRun).where(IntegrationSyncRun.provider == "ACESSORIAS")).all()

    assert company_calls["count"] == 2
    assert first.status == "SUCCESS"
    assert second.status == "SUCCESS"
    assert first.summary["periods_success"] == 3
    assert first.summary["deliveries_received"] == 9
    assert first.summary["tasks_skipped"] == 3
    assert first.summary["unmapped_obligations"] == 6
    assert first.summary["companies_received"] == 2
    assert first.summary["companies_matched"] == 1
    assert first.summary["companies_unmatched"] == 1
    assert first.summary["regimes_mapped"] == 1
    assert first.summary["regimes_unmapped"] == 1
    assert len(company_snapshots) == 2
    assert len(delivery_snapshots) == 9
    assert len(statuses) == 3
    assert len(runs) == 6
    assert all(run.run_metadata["backfill"] is True for run in runs)
    assert all(run.run_metadata["from_period"] == "2025-12" for run in runs)
    assert all(run.run_metadata["to_period"] == "2026-02" for run in runs)
    assert {run.run_metadata["current_period"] for run in runs} == {"2025-12", "2026-01", "2026-02"}
    assert statuses[0].company_id == company.id


def test_backfill_supports_skip_companies_and_dry_run_without_writes(db_session) -> None:
    organization, _ = _seed_org_company_periods(db_session)

    result = backfill_acessorias(
        db_session,
        organization=organization,
        from_period="2026-06",
        to_period="2026-06",
        skip_companies=True,
        dry_run=True,
        client=_fixture_client(),
    )

    assert result.status == "SUCCESS"
    assert result.summary["companies_received"] == 0
    assert db_session.scalars(select(AcessoriasCompanySnapshot)).all() == []
    assert db_session.scalars(select(AcessoriasDeliverySnapshot)).all() == []
    assert db_session.scalars(select(FiscalObligationStatus)).all() == []
    assert db_session.scalars(select(IntegrationSyncRun)).all() == []


def test_backfill_fiscal_only_filters_non_fiscal_snapshots(db_session) -> None:
    organization, _ = _seed_org_company_periods(db_session)

    result = backfill_acessorias(
        db_session,
        organization=organization,
        from_period="2026-06",
        to_period="2026-06",
        fiscal_only=True,
        client=_fixture_client(),
    )

    delivery_snapshots = db_session.scalars(select(AcessoriasDeliverySnapshot)).all()

    assert result.status == "SUCCESS"
    assert result.summary["deliveries_received"] == 3
    assert result.summary["deliveries_filtered_out"] == 1
    assert len(delivery_snapshots) == 2


def test_backfill_continues_after_period_failure_when_stop_on_error_is_false(db_session) -> None:
    organization, _ = _seed_org_company_periods(db_session)

    class FlakyClient(FixtureAcessoriasClient):
        def iter_deliveries(self, identifier: str, *, dt_initial: date, dt_final: date):
            if dt_initial.strftime("%Y-%m") == "2026-01":
                raise RuntimeError("fixture token should stay hidden")
            return super().iter_deliveries(identifier, dt_initial=dt_initial, dt_final=dt_final)

    client = FlakyClient(
        companies=_fixture_client()._companies,
        deliveries_by_period=_fixture_client()._deliveries_by_period,
    )

    result = backfill_acessorias(
        db_session,
        organization=organization,
        from_period="2025-12",
        to_period="2026-02",
        client=client,
        stop_on_error=False,
    )

    assert result.status == "PARTIAL"
    assert result.summary["periods_success"] == 2
    assert result.summary["periods_failed"] == 1
    assert "fixture token should stay hidden" in result.errors[-1]["error"]


def test_backfill_stop_on_error_interrupts_range(db_session) -> None:
    organization, _ = _seed_org_company_periods(db_session)

    class FlakyClient(FixtureAcessoriasClient):
        def iter_deliveries(self, identifier: str, *, dt_initial: date, dt_final: date):
            if dt_initial.strftime("%Y-%m") == "2026-01":
                raise RuntimeError("period failure")
            return super().iter_deliveries(identifier, dt_initial=dt_initial, dt_final=dt_final)

    client = FlakyClient(
        companies=_fixture_client()._companies,
        deliveries_by_period=_fixture_client()._deliveries_by_period,
    )

    with pytest.raises(RuntimeError, match="status 'FAILED'"):
        backfill_acessorias(
            db_session,
            organization=organization,
            from_period="2025-12",
            to_period="2026-02",
            client=client,
            stop_on_error=True,
        )


def test_backfill_rejects_company_from_other_tenant(db_session) -> None:
    organization, _ = _seed_org_company_periods(db_session)
    other_org = Organization(name="Other", slug="other-org")
    db_session.add(other_org)
    db_session.flush()
    foreign_company = ExternalCompany(
        organization_id=other_org.id,
        cnpj="99999999000199",
        razao_social="Other Ltda",
        active=True,
    )
    db_session.add(foreign_company)
    db_session.flush()

    with pytest.raises(ValueError, match="Company"):
        backfill_acessorias(
            db_session,
            organization=organization,
            from_period="2026-06",
            to_period="2026-06",
            company_id=foreign_company.id,
            client=_fixture_client(),
        )
