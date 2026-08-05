from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.app.models.company_cnae import CompanyCnae
from backend.app.models.econet_cnae_cache import EconetCnaeCache
from backend.app.models.external_company import ExternalCompany
from backend.app.models.organization import Organization
from backend.app.services.integrations.econet.enrichment import _resolve_target_cnaes, enrich_cnaes


def test_resolve_target_cnaes_ignores_placeholder_zero_for_explicit_list(db_session) -> None:
    resolved = _resolve_target_cnaes(
        db_session,
        organization_id=1,
        explicit_cnaes=["0000-0/00", "7020-4/00"],
        company_ids=None,
    )
    assert resolved == ["7020400"]


def test_old_parser_version_is_not_complete_in_cache_only(db_session) -> None:
    now = datetime.now(timezone.utc)
    db_session.add(
        EconetCnaeCache(
            cnae="7020400",
            cnae_formatted="7020-4/00",
            description="consultoria em gestão empresarial",
            econet_id_cnae="123",
            activity_types=[],
            simples_status="ALLOWED",
            simples_allowed=True,
            simples_annex_default="V",
            simples_annex_conditional="III",
            factor_r_applicable=True,
            factor_r_threshold="28.00",
            mei_status="NOT_ALLOWED",
            mei_allowed=False,
            mei_occupation=None,
            presumed_profit_status="ALLOWED",
            presumed_profit_allowed=True,
            presumed_profit_irpj_rate=None,
            presumed_profit_csll_rate=None,
            actual_profit_status="UNKNOWN",
            actual_profit_mandatory=None,
            obligations_general={},
            obligations_simples={},
            obligations_simei={},
            unmapped_obligations=[],
            normalized_payload={},
            parse_status="PARSED",
            parser_version="1",
            content_hash="a" * 64,
            retrieved_at=now,
            expires_at=now + timedelta(days=30),
        )
    )
    db_session.flush()

    result = enrich_cnaes(
        db_session,
        organization_id=1,
        cnaes=["7020400"],
        cache_only=True,
        sync_catalog=False,
        classify_companies=False,
    )

    assert result.status == "SUCCESS"
    assert result.items[0].status == "STALE_PARSER_VERSION"


def test_cache_only_stale_parser_version_has_specific_status(db_session) -> None:
    now = datetime.now(timezone.utc)
    db_session.add(
        EconetCnaeCache(
            cnae="8593700",
            cnae_formatted="8593-7/00",
            description="cache antigo",
            econet_id_cnae="123",
            activity_types=[],
            simples_status="ALLOWED",
            simples_allowed=True,
            simples_annex_default="III",
            simples_annex_conditional=None,
            factor_r_applicable=False,
            factor_r_threshold=None,
            mei_status="NOT_ALLOWED",
            mei_allowed=False,
            mei_occupation=None,
            presumed_profit_status="ALLOWED",
            presumed_profit_allowed=True,
            presumed_profit_irpj_rate=None,
            presumed_profit_csll_rate=None,
            actual_profit_status="UNKNOWN",
            actual_profit_mandatory=None,
            obligations_general={},
            obligations_simples={},
            obligations_simei={},
            unmapped_obligations=[],
            normalized_payload={},
            parse_status="PARSED",
            parser_version="1",
            content_hash="b" * 64,
            retrieved_at=now,
            expires_at=now + timedelta(days=30),
        )
    )
    db_session.flush()

    result = enrich_cnaes(
        db_session,
        organization_id=1,
        cnaes=["8593700"],
        cache_only=True,
        force_refresh=True,
        sync_catalog=False,
        classify_companies=False,
    )

    assert result.items[0].status == "STALE_PARSER_VERSION"


def test_enrichment_returns_factor_r_results_for_company_ids(db_session) -> None:
    organization = Organization(name="Org Factor R", slug="org-factor-r")
    db_session.add(organization)
    db_session.flush()
    company = ExternalCompany(
        organization_id=organization.id,
        cnpj="19163109000178",
        razao_social="Empresa Factor R",
        active=True,
    )
    db_session.add(company)
    db_session.flush()
    db_session.add(
        CompanyCnae(
            company_id=company.id,
            cnae="7020400",
            cnae_formatted="7020-4/00",
            is_primary=True,
            source="ECONTROLE",
            active=True,
            first_seen_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
    )
    now = datetime.now(timezone.utc)
    db_session.add(
        EconetCnaeCache(
            cnae="7020400",
            cnae_formatted="7020-4/00",
            description="consultoria em gestao empresarial",
            econet_id_cnae="123",
            activity_types=[],
            simples_status="ALLOWED",
            simples_allowed=True,
            simples_annex_default="V",
            simples_annex_conditional="III",
            factor_r_applicable=True,
            factor_r_threshold="28.00",
            mei_status="NOT_ALLOWED",
            mei_allowed=False,
            mei_occupation=None,
            presumed_profit_status="ALLOWED",
            presumed_profit_allowed=True,
            presumed_profit_irpj_rate=None,
            presumed_profit_csll_rate=None,
            actual_profit_status="UNKNOWN",
            actual_profit_mandatory=None,
            obligations_general={},
            obligations_simples={},
            obligations_simei={},
            unmapped_obligations=[],
            normalized_payload={},
            parse_status="PARSED",
            parser_version="econet-html-v2",
            content_hash="c" * 64,
            retrieved_at=now,
            expires_at=now + timedelta(days=30),
        )
    )
    db_session.flush()

    result = enrich_cnaes(
        db_session,
        organization_id=organization.id,
        company_ids=[company.id],
        sync_catalog=False,
        classify_companies=False,
        dry_run=False,
    )

    assert result.status == "SUCCESS"
    assert result.factor_r_results is not None
    assert len(result.factor_r_results) == 1
    assert result.factor_r_results[0].company_id == company.id
    assert result.factor_r_results[0].factor_r_potential is True
    assert result.factor_r_results[0].factor_r_threshold == Decimal("28.00")
