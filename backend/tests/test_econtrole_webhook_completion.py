from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from backend.app.core.config import get_settings
from backend.app.models.company_activity_type import CompanyActivityType
from backend.app.models.company_cnae import CompanyCnae
from backend.app.models.econet_cnae_cache import EconetCnaeCache
from backend.app.models.external_company import ExternalCompany
from backend.app.models.integration_sync_run import IntegrationSyncRun
from backend.app.models.organization import Organization
from backend.app.services.integrations.acessorias.sync import AcessoriasCompanySyncResult
from backend.app.services.integrations.econtrole.sync import upsert_company_from_econtrole_payload
from backend.app.services.integrations.econtrole.webhook_completion import (
    ACESSORIAS_RETRY_MAX_ATTEMPTS,
    ACESSORIAS_RETRY_JOB_NAME,
    complete_company_after_econtrole_webhook,
    process_due_acessorias_retries,
)


def _create_org(db_session, slug: str = "org-webhook-completion") -> Organization:
    organization = Organization(name="Org Webhook Completion", slug=slug)
    db_session.add(organization)
    db_session.flush()
    return organization


def _payload(**overrides):
    payload = {
        "id": "123",
        "profile_id": "456",
        "cnpj": "19.163.109/0001-78",
        "razao_social": "AC SOARES LTDA",
        "nome_fantasia": "AC Soares",
        "situacao": "ATIVA",
        "municipio": "Anapolis",
        "uf": "GO",
        "cnae_principal": "4711-3/02",
        "cnaes_secundarios": ["8630-5/03"],
        "updated_at": "2026-07-07T10:00:00-03:00",
    }
    payload.update(overrides)
    return payload


def test_upsert_marks_company_inactive_when_situacao_is_inativa(db_session) -> None:
    organization = _create_org(db_session)

    result = upsert_company_from_econtrole_payload(
        db_session,
        organization=organization,
        payload=_payload(situacao="Inativa"),
    )

    company = db_session.scalar(select(ExternalCompany).where(ExternalCompany.id == result.company.id))
    active_cnaes = db_session.scalars(
        select(CompanyCnae).where(CompanyCnae.company_id == result.company.id, CompanyCnae.active.is_(True))
    ).all()

    assert company is not None
    assert company.active is False
    assert company.sync_status == "INACTIVE_ECONTROLE"
    assert active_cnaes == []


def test_upsert_inactive_clears_company_activity_types(db_session) -> None:
    organization = _create_org(db_session, slug="org-webhook-completion-2")
    created = upsert_company_from_econtrole_payload(
        db_session,
        organization=organization,
        payload=_payload(),
    )

    rows_before = db_session.scalars(select(CompanyActivityType).where(CompanyActivityType.company_id == created.company.id)).all()
    upsert_company_from_econtrole_payload(
        db_session,
        organization=organization,
        payload=_payload(situacao="INATIVA"),
    )
    rows_after = db_session.scalars(select(CompanyActivityType).where(CompanyActivityType.company_id == created.company.id)).all()

    assert rows_before
    assert rows_after == []


def test_webhook_completion_schedules_acessorias_retry_when_company_is_missing(db_session, monkeypatch) -> None:
    monkeypatch.setenv("ACESSORIAS_API_TOKEN", "test-token")
    get_settings.cache_clear()
    organization = _create_org(db_session, slug="org-webhook-completion-3")
    company = ExternalCompany(
        organization_id=organization.id,
        cnpj="19163109000178",
        razao_social="AC SOARES LTDA",
        active=True,
    )
    db_session.add(company)
    db_session.flush()

    def _fake_from_settings(settings):
        return object()

    def _fake_sync_company(session, *, organization, identifier, client, dry_run=False):
        return AcessoriasCompanySyncResult(payloads_found=0, summary={}, errors=[], dry_run=dry_run)

    monkeypatch.setattr(
        "backend.app.services.integrations.econtrole.webhook_completion.AcessoriasClient.from_settings",
        _fake_from_settings,
    )
    monkeypatch.setattr(
        "backend.app.services.integrations.econtrole.webhook_completion.sync_acessorias_company",
        _fake_sync_company,
    )

    result = complete_company_after_econtrole_webhook(db_session, organization=organization, company=company)
    pending = db_session.scalar(
        select(IntegrationSyncRun).where(
            IntegrationSyncRun.organization_id == organization.id,
            IntegrationSyncRun.provider == "ACESSORIAS",
            IntegrationSyncRun.job_name == ACESSORIAS_RETRY_JOB_NAME,
        )
    )

    assert result.acessorias_status == "RETRY_SCHEDULED"
    assert result.acessorias_retry_scheduled is True
    assert pending is not None
    assert pending.status == "PENDING"
    assert pending.run_metadata["company_id"] == company.id
    get_settings.cache_clear()


def test_webhook_completion_cancels_pending_retry_after_acessorias_success(db_session, monkeypatch) -> None:
    monkeypatch.setenv("ACESSORIAS_API_TOKEN", "test-token")
    get_settings.cache_clear()
    organization = _create_org(db_session, slug="org-webhook-completion-4")
    company = ExternalCompany(
        organization_id=organization.id,
        cnpj="19163109000178",
        razao_social="AC SOARES LTDA",
        active=True,
    )
    db_session.add(company)
    db_session.flush()
    db_session.add(
        IntegrationSyncRun(
            organization_id=organization.id,
            integration_account_id=None,
            provider="ACESSORIAS",
            job_name=ACESSORIAS_RETRY_JOB_NAME,
            status="PENDING",
            run_metadata={"company_id": company.id, "cnpj": company.cnpj},
            summary={"reason": "company_not_available_in_acessorias_yet"},
        )
    )
    db_session.flush()

    def _fake_from_settings(settings):
        return object()

    def _fake_sync_company(session, *, organization, identifier, client, dry_run=False):
        return AcessoriasCompanySyncResult(payloads_found=1, summary={"companies_matched": 1}, errors=[], dry_run=dry_run)

    monkeypatch.setattr(
        "backend.app.services.integrations.econtrole.webhook_completion.AcessoriasClient.from_settings",
        _fake_from_settings,
    )
    monkeypatch.setattr(
        "backend.app.services.integrations.econtrole.webhook_completion.sync_acessorias_company",
        _fake_sync_company,
    )

    result = complete_company_after_econtrole_webhook(db_session, organization=organization, company=company)
    pending = db_session.scalar(
        select(IntegrationSyncRun).where(
            IntegrationSyncRun.organization_id == organization.id,
            IntegrationSyncRun.provider == "ACESSORIAS",
            IntegrationSyncRun.job_name == ACESSORIAS_RETRY_JOB_NAME,
        )
    )

    assert result.acessorias_status == "SYNCED"
    assert result.acessorias_retry_scheduled is False
    assert pending is not None
    assert pending.status == "CANCELLED"
    assert pending.finished_at is not None
    get_settings.cache_clear()


def test_webhook_completion_enriches_only_missing_cnaes_from_econet(db_session, monkeypatch) -> None:
    monkeypatch.setenv("ECONET_ASSISTED_SESSION_ENABLED", "1")
    get_settings.cache_clear()
    organization = _create_org(db_session, slug="org-webhook-completion-5")
    company = ExternalCompany(
        organization_id=organization.id,
        cnpj="19163109000178",
        razao_social="AC SOARES LTDA",
        active=True,
    )
    db_session.add(company)
    db_session.flush()
    db_session.add_all(
        [
            CompanyCnae(
                company_id=company.id,
                cnae="4711302",
                cnae_formatted="4711-3/02",
                is_primary=True,
                source="ECONTROLE",
                active=True,
                first_seen_at=company.created_at,
                last_seen_at=company.created_at,
                deactivated_at=None,
            ),
            CompanyCnae(
                company_id=company.id,
                cnae="8630503",
                cnae_formatted="8630-5/03",
                is_primary=False,
                source="ECONTROLE",
                active=True,
                first_seen_at=company.created_at,
                last_seen_at=company.created_at,
                deactivated_at=None,
            ),
        ]
    )
    db_session.flush()

    db_session.add(
        EconetCnaeCache(
            cnae="4711302",
            cnae_formatted="4711-3/02",
            description="Comercio varejista",
            econet_id_cnae="econet-4711302",
            activity_types=["COMERCIO"],
            simples_status="ALLOWED",
            simples_allowed=True,
            simples_annex_default="I",
            simples_annex_conditional=None,
            factor_r_applicable=False,
            factor_r_threshold=None,
            mei_status="NOT_APPLICABLE",
            mei_allowed=None,
            mei_occupation=None,
            presumed_profit_status="ALLOWED",
            presumed_profit_allowed=True,
            presumed_profit_irpj_rate=None,
            presumed_profit_csll_rate=None,
            actual_profit_status="OPTIONAL",
            actual_profit_mandatory=False,
            obligations_general={},
            obligations_simples={},
            obligations_simei={},
            unmapped_obligations=[],
            normalized_payload={},
            parse_status="PARSED",
            parser_version="econet-html-v2",
            content_hash="hash",
            retrieved_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc),
        )
    )
    db_session.flush()

    captured: dict[str, object] = {}

    class _FakeResult:
        status = "SUCCESS"

    def _fake_enrich(session, **kwargs):
        captured.update(kwargs)
        return _FakeResult()

    monkeypatch.setattr(
        "backend.app.services.integrations.econtrole.webhook_completion.enrich_cnaes",
        _fake_enrich,
    )

    result = complete_company_after_econtrole_webhook(db_session, organization=organization, company=company)

    assert result.econet_status == "SUCCESS"
    assert result.econet_missing_cnaes == 1
    assert captured["cnaes"] == ["8630503"]
    assert captured["company_ids"] == [company.id]
    get_settings.cache_clear()


def test_process_due_acessorias_retries_marks_success(db_session, monkeypatch) -> None:
    monkeypatch.setenv("ACESSORIAS_API_TOKEN", "test-token")
    get_settings.cache_clear()
    organization = _create_org(db_session, slug="org-webhook-completion-6")
    company = ExternalCompany(
        organization_id=organization.id,
        cnpj="19163109000178",
        razao_social="AC SOARES LTDA",
        active=True,
    )
    db_session.add(company)
    db_session.flush()
    run = IntegrationSyncRun(
        organization_id=organization.id,
        integration_account_id=None,
        provider="ACESSORIAS",
        job_name=ACESSORIAS_RETRY_JOB_NAME,
        status="PENDING",
        run_metadata={"company_id": company.id, "cnpj": company.cnpj, "organization_slug": organization.slug, "attempt_count": 0},
        summary={"retry_after": "2026-08-19T10:00:00+00:00"},
    )
    db_session.add(run)
    db_session.flush()

    monkeypatch.setattr(
        "backend.app.services.integrations.econtrole.webhook_completion.AcessoriasClient.from_settings",
        lambda settings: object(),
    )
    monkeypatch.setattr(
        "backend.app.services.integrations.econtrole.webhook_completion.sync_acessorias_company",
        lambda session, organization, identifier, client, dry_run=False: AcessoriasCompanySyncResult(
            payloads_found=1,
            summary={},
            errors=[],
            dry_run=dry_run,
        ),
    )

    result = process_due_acessorias_retries(db_session, now=datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc))
    db_session.flush()
    refreshed = db_session.get(IntegrationSyncRun, run.id)

    assert result.succeeded == 1
    assert refreshed is not None
    assert refreshed.status == "SUCCESS"
    assert refreshed.finished_at is not None
    get_settings.cache_clear()


def test_process_due_acessorias_retries_reschedules_when_still_missing(db_session, monkeypatch) -> None:
    monkeypatch.setenv("ACESSORIAS_API_TOKEN", "test-token")
    get_settings.cache_clear()
    organization = _create_org(db_session, slug="org-webhook-completion-7")
    company = ExternalCompany(
        organization_id=organization.id,
        cnpj="19163109000178",
        razao_social="AC SOARES LTDA",
        active=True,
    )
    db_session.add(company)
    db_session.flush()
    run = IntegrationSyncRun(
        organization_id=organization.id,
        integration_account_id=None,
        provider="ACESSORIAS",
        job_name=ACESSORIAS_RETRY_JOB_NAME,
        status="PENDING",
        run_metadata={"company_id": company.id, "cnpj": company.cnpj, "organization_slug": organization.slug, "attempt_count": 1},
        summary={"retry_after": "2026-08-19T10:00:00+00:00"},
    )
    db_session.add(run)
    db_session.flush()

    monkeypatch.setattr(
        "backend.app.services.integrations.econtrole.webhook_completion.AcessoriasClient.from_settings",
        lambda settings: object(),
    )
    monkeypatch.setattr(
        "backend.app.services.integrations.econtrole.webhook_completion.sync_acessorias_company",
        lambda session, organization, identifier, client, dry_run=False: AcessoriasCompanySyncResult(
            payloads_found=0,
            summary={},
            errors=[],
            dry_run=dry_run,
        ),
    )

    result = process_due_acessorias_retries(db_session, now=datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc))
    db_session.flush()
    refreshed = db_session.get(IntegrationSyncRun, run.id)

    assert result.rescheduled == 1
    assert refreshed is not None
    assert refreshed.status == "PENDING"
    assert refreshed.run_metadata["attempt_count"] == 2
    assert "retry_after" in refreshed.summary
    get_settings.cache_clear()


def test_process_due_acessorias_retries_exhausts_after_max_attempts(db_session, monkeypatch) -> None:
    monkeypatch.setenv("ACESSORIAS_API_TOKEN", "test-token")
    get_settings.cache_clear()
    organization = _create_org(db_session, slug="org-webhook-completion-8")
    company = ExternalCompany(
        organization_id=organization.id,
        cnpj="19163109000178",
        razao_social="AC SOARES LTDA",
        active=True,
    )
    db_session.add(company)
    db_session.flush()
    run = IntegrationSyncRun(
        organization_id=organization.id,
        integration_account_id=None,
        provider="ACESSORIAS",
        job_name=ACESSORIAS_RETRY_JOB_NAME,
        status="PENDING",
        run_metadata={
            "company_id": company.id,
            "cnpj": company.cnpj,
            "organization_slug": organization.slug,
            "attempt_count": ACESSORIAS_RETRY_MAX_ATTEMPTS - 1,
        },
        summary={"retry_after": "2026-08-19T10:00:00+00:00"},
    )
    db_session.add(run)
    db_session.flush()

    monkeypatch.setattr(
        "backend.app.services.integrations.econtrole.webhook_completion.AcessoriasClient.from_settings",
        lambda settings: object(),
    )
    monkeypatch.setattr(
        "backend.app.services.integrations.econtrole.webhook_completion.sync_acessorias_company",
        lambda session, organization, identifier, client, dry_run=False: AcessoriasCompanySyncResult(
            payloads_found=0,
            summary={},
            errors=[],
            dry_run=dry_run,
        ),
    )

    result = process_due_acessorias_retries(db_session, now=datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc))
    db_session.flush()
    refreshed = db_session.get(IntegrationSyncRun, run.id)

    assert result.exhausted == 1
    assert refreshed is not None
    assert refreshed.status == "EXHAUSTED"
    get_settings.cache_clear()


def test_process_due_acessorias_retries_cancels_for_inactive_company(db_session) -> None:
    organization = _create_org(db_session, slug="org-webhook-completion-9")
    company = ExternalCompany(
        organization_id=organization.id,
        cnpj="19163109000178",
        razao_social="AC SOARES LTDA",
        active=False,
    )
    db_session.add(company)
    db_session.flush()
    run = IntegrationSyncRun(
        organization_id=organization.id,
        integration_account_id=None,
        provider="ACESSORIAS",
        job_name=ACESSORIAS_RETRY_JOB_NAME,
        status="PENDING",
        run_metadata={"company_id": company.id, "cnpj": company.cnpj, "organization_slug": organization.slug, "attempt_count": 0},
        summary={"retry_after": "2026-08-19T10:00:00+00:00"},
    )
    db_session.add(run)
    db_session.flush()

    result = process_due_acessorias_retries(db_session, now=datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc))
    db_session.flush()
    refreshed = db_session.get(IntegrationSyncRun, run.id)

    assert result.cancelled == 1
    assert refreshed is not None
    assert refreshed.status == "CANCELLED"
