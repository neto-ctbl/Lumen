from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import select

from backend.app.models.external_company import ExternalCompany
from backend.app.models.integration_sync_run import IntegrationSyncRun
from backend.app.models.organization import Organization
from backend.app.models.sittax_company_snapshot import SittaxCompanySnapshot
from backend.app.services.integrations.sittax import FixtureSittaxClient, SittaxClient, SittaxSession
from backend.app.services.integrations.sittax.errors import (
    SittaxAuthenticationError,
    SittaxTransportError,
)
from backend.app.services.integrations.sittax.sync import (
    AMBIGUOUS,
    MATCHED,
    build_fixture_sittax_client,
    reconcile_external_company_candidates,
    sync_sittax_companies,
)


FIXTURES_DIR = Path("backend/tests/fixtures/sittax")


def _seed_organization(db_session) -> Organization:
    organization = Organization(name="Org Sittax", slug="org-sittax")
    db_session.add(organization)
    db_session.flush()
    return organization


def _seed_external_company(db_session, organization: Organization, *, cnpj: str = "12345678000195") -> ExternalCompany:
    company = ExternalCompany(
        organization_id=organization.id,
        cnpj=cnpj,
        razao_social="Empresa Local",
        nome_fantasia="Local",
        active=True,
    )
    db_session.add(company)
    db_session.flush()
    return company


def _fixture_client() -> FixtureSittaxClient:
    return build_fixture_sittax_client(companies_fixture=FIXTURES_DIR / "companies_success.json")


class FakeSittaxClient:
    def __init__(self, payloads: list[dict[str, Any]], *, auth_error: Exception | None = None) -> None:
        self.session = SittaxSession.from_settings
        self._payloads = payloads
        self._auth_error = auth_error
        self.closed = False
        self._inner_session = SittaxSession.from_settings(__import__("backend.app.core.config", fromlist=["get_settings"]).get_settings())

    @property
    def session(self) -> SittaxSession:
        return self._inner_session

    @session.setter
    def session(self, value) -> None:
        del value

    def authenticate_with_settings(self, settings) -> None:
        del settings
        if self._auth_error is not None:
            raise self._auth_error
        self._inner_session.mark_authenticated(
            token="fixture-token",
            office_id="esc-1",
            office_name="Escritorio",
            user_id="user-1",
            user_role="DEV",
        )

    def list_companies_payloads(self) -> list[dict[str, Any]]:
        return list(self._payloads)

    def close(self) -> None:
        self.closed = True
        self._inner_session.close()


def test_sync_creates_snapshots_and_is_idempotent(db_session) -> None:
    organization = _seed_organization(db_session)
    company = _seed_external_company(db_session, organization)

    first = sync_sittax_companies(db_session, organization=organization, client=_fixture_client())
    snapshots_before = db_session.scalars(select(SittaxCompanySnapshot).order_by(SittaxCompanySnapshot.sittax_company_id)).all()
    first_seen = snapshots_before[0].first_seen_at
    last_seen = snapshots_before[0].last_seen_at

    second = sync_sittax_companies(db_session, organization=organization, client=_fixture_client())
    snapshots_after = db_session.scalars(select(SittaxCompanySnapshot).order_by(SittaxCompanySnapshot.sittax_company_id)).all()
    runs = db_session.scalars(select(IntegrationSyncRun).where(IntegrationSyncRun.provider == "SITTAX")).all()

    assert first.status == "SUCCESS"
    assert second.status == "SUCCESS"
    assert len(snapshots_after) == 2
    assert len(runs) == 2
    assert snapshots_after[0].company_id == company.id
    assert snapshots_after[0].match_status == MATCHED
    assert snapshots_after[0].first_seen_at == first_seen
    assert snapshots_after[0].last_seen_at >= last_seen
    assert second.summary["snapshots_created"] == 0
    assert second.summary["snapshots_updated"] == 0
    assert second.summary["snapshots_unchanged"] == 2


def test_sync_updates_existing_snapshot_when_payload_changes(db_session) -> None:
    organization = _seed_organization(db_session)
    _seed_external_company(db_session, organization)

    sync_sittax_companies(db_session, organization=organization, client=_fixture_client())

    changed_payload = [
        {
            "id": "emp-sittax-001",
            "cnpj": "12345678000195",
            "nome": "EMPRESA EXEMPLO A LTDA",
            "fantasia": "EMPRESA ALTERADA",
            "uf": "GO",
            "inscricaoEstadual": "IE-SINT-9999",
            "homologada": True,
            "usaRegimeDeCaixa": False,
        }
    ]
    result = sync_sittax_companies(
        db_session,
        organization=organization,
        client=FakeSittaxClient(changed_payload),
    )
    snapshot = db_session.scalar(
        select(SittaxCompanySnapshot).where(SittaxCompanySnapshot.sittax_company_id == "emp-sittax-001")
    )

    assert result.summary["snapshots_updated"] == 1
    assert snapshot is not None
    assert snapshot.trade_name == "EMPRESA ALTERADA"
    assert snapshot.state_registration == "IE-SINT-9999"


def test_sync_supports_dry_run_without_writes(db_session) -> None:
    organization = _seed_organization(db_session)
    _seed_external_company(db_session, organization)

    result = sync_sittax_companies(
        db_session,
        organization=organization,
        dry_run=True,
        client=_fixture_client(),
    )

    assert result.status == "DRY_RUN"
    assert result.run is None
    assert db_session.scalars(select(SittaxCompanySnapshot)).all() == []
    assert db_session.scalars(select(IntegrationSyncRun)).all() == []


def test_sync_marks_invalid_cnpj_as_partial_without_pii(db_session) -> None:
    organization = _seed_organization(db_session)
    _seed_external_company(db_session, organization)

    result = sync_sittax_companies(
        db_session,
        organization=organization,
        client=FakeSittaxClient(
            [
                {
                    "id": "emp-sittax-001",
                    "cnpj": "12345678000195",
                    "nome": "EMPRESA EXEMPLO A LTDA",
                    "fantasia": "EMPRESA EXEMPLO A",
                    "uf": "GO",
                    "inscricaoEstadual": "IE-SINT-0001",
                    "homologada": True,
                    "usaRegimeDeCaixa": False,
                },
                {
                    "id": "emp-sittax-999",
                    "cnpj": "123",
                    "nome": "INVALIDA",
                    "fantasia": "INVALIDA",
                    "uf": "GO",
                    "inscricaoEstadual": None,
                    "homologada": False,
                    "usaRegimeDeCaixa": False,
                },
            ]
        ),
    )

    assert result.status == "PARTIAL"
    assert result.summary["companies_invalid"] == 1
    assert result.errors[0]["match_status"] == "INVALID_CNPJ"
    assert "12345678000195" not in str(result.errors)


def test_sync_handles_empty_list_as_success(db_session) -> None:
    organization = _seed_organization(db_session)

    result = sync_sittax_companies(
        db_session,
        organization=organization,
        client=FakeSittaxClient([]),
    )

    assert result.status == "SUCCESS"
    assert result.summary["companies_received"] == 0


@pytest.mark.parametrize("error", [SittaxAuthenticationError("bad credentials"), SittaxTransportError("network down")])
def test_sync_marks_run_as_failed_on_top_level_errors(db_session, error: Exception) -> None:
    organization = _seed_organization(db_session)

    with pytest.raises(error.__class__):
        sync_sittax_companies(
            db_session,
            organization=organization,
            client=FakeSittaxClient([], auth_error=error),
        )

    run = db_session.scalar(select(IntegrationSyncRun).where(IntegrationSyncRun.provider == "SITTAX"))
    assert run is not None
    assert run.status == "FAILED"
    assert run.summary is not None
    assert "bad credentials" not in str(run.errors)
    assert "network down" not in str(run.errors)


def test_sync_can_record_ambiguous_match_without_choosing_first(db_session, monkeypatch) -> None:
    organization = _seed_organization(db_session)

    monkeypatch.setattr(
        "backend.app.services.integrations.sittax.sync._reconcile_external_company",
        lambda session, organization_id, cnpj: type("Match", (), {"company_id": None, "match_status": AMBIGUOUS})(),
    )

    result = sync_sittax_companies(db_session, organization=organization, client=_fixture_client())
    snapshot = db_session.scalar(
        select(SittaxCompanySnapshot).where(SittaxCompanySnapshot.sittax_company_id == "emp-sittax-001")
    )

    assert result.summary["companies_ambiguous"] == 2
    assert snapshot is not None
    assert snapshot.company_id is None
    assert snapshot.match_status == AMBIGUOUS


def test_reconcile_candidates_supports_ambiguous_branch() -> None:
    candidates = [
        ExternalCompany(id=1, organization_id=1, cnpj="12345678000195", razao_social="A", active=True),
        ExternalCompany(id=2, organization_id=1, cnpj="12345678000195", razao_social="B", active=True),
    ]

    match = reconcile_external_company_candidates(candidates)

    assert match.company_id is None
    assert match.match_status == AMBIGUOUS


def test_sync_uses_only_login_and_companies_endpoints(db_session) -> None:
    organization = _seed_organization(db_session)
    _seed_external_company(db_session, organization)
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        if request.url.path == "/api/auth/login":
            return httpx.Response(
                200,
                json={
                    "codigo": 200,
                    "token": "jwt-fixture-token",
                    "usuario": {"id": "1", "role": "DEV", "escritorio": {"id": "esc-1", "nome": "Escritorio"}},
                },
            )
        if request.url.path == "/api/empresa/listar-todas-escritorio-empresas-selecao":
            return httpx.Response(200, json={"sucesso": True, "empresas": [__import__("json").loads((FIXTURES_DIR / "companies_success.json").read_text(encoding="utf-8"))["empresas"][0]]})
        raise AssertionError(f"Unexpected path {request.url.path}")

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    session = SittaxSession.from_settings(__import__("backend.app.core.config", fromlist=["get_settings"]).get_settings(), http_client=http_client)
    client = SittaxClient(session=session)

    result = sync_sittax_companies(db_session, organization=organization, client=client)

    assert result.status == "SUCCESS"
    assert requested_paths == [
        "/api/auth/login",
        "/api/empresa/listar-todas-escritorio-empresas-selecao",
    ]
    client.close()
