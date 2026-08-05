from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.app.models.company_cnae import CompanyCnae
from backend.app.models.econet_cnae_cache import EconetCnaeCache
from backend.app.models.external_company import ExternalCompany
from backend.app.models.organization import Organization
from backend.app.services.factor_r import get_company_factor_r_potential
from backend.app.services.integrations.econet.parser import CURRENT_ECONET_PARSER_VERSION


def _create_company(db_session) -> ExternalCompany:
    organization = Organization(name="Org Factor R Local", slug=f"org-factor-r-local-{datetime.now(timezone.utc).timestamp()}")
    db_session.add(organization)
    db_session.flush()
    company = ExternalCompany(
        organization_id=organization.id,
        cnpj="19163109000178",
        razao_social="Empresa Factor R Local",
        active=True,
    )
    db_session.add(company)
    db_session.flush()
    return company


def _add_company_cnae(db_session, *, company_id: int, cnae: str) -> None:
    db_session.add(
        CompanyCnae(
            company_id=company_id,
            cnae=cnae,
            cnae_formatted=f"{cnae[:4]}-{cnae[4]}/{cnae[5:]}",
            is_primary=True,
            source="ECONTROLE",
            active=True,
            first_seen_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
    )


def _add_cache(
    db_session,
    *,
    cnae: str,
    simples_status: str = "ALLOWED",
    simples_allowed: bool | None = True,
    annex_default: str | None = None,
    annex_conditional: str | None = None,
    factor_r_applicable: bool | None = None,
    factor_r_threshold: Decimal | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    db_session.add(
        EconetCnaeCache(
            cnae=cnae,
            cnae_formatted=f"{cnae[:4]}-{cnae[4]}/{cnae[5:]}",
            description=f"Descricao {cnae}",
            econet_id_cnae=f"id-{cnae}",
            activity_types=[],
            simples_status=simples_status,
            simples_allowed=simples_allowed,
            simples_annex_default=annex_default,
            simples_annex_conditional=annex_conditional,
            factor_r_applicable=factor_r_applicable,
            factor_r_threshold=factor_r_threshold,
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
            content_hash=(cnae * 10)[:64],
            retrieved_at=now,
            expires_at=now + timedelta(days=30),
        )
    )


def test_factor_r_infers_not_applicable_for_annex_iv(db_session) -> None:
    company = _create_company(db_session)
    _add_company_cnae(db_session, company_id=company.id, cnae="4120400")
    _add_cache(db_session, cnae="4120400", annex_default="IV")
    db_session.flush()

    result = get_company_factor_r_potential(db_session, company_id=company.id)

    assert result.status == "NOT_APPLICABLE"
    assert result.factor_r_potential is False
    assert result.cnaes_with_cache == 1
    assert result.missing_cnaes == []
    assert result.negative_cnaes == ["4120400"]


def test_factor_r_infers_not_applicable_for_prohibited_simples(db_session) -> None:
    company = _create_company(db_session)
    _add_company_cnae(db_session, company_id=company.id, cnae="6810202")
    _add_cache(
        db_session,
        cnae="6810202",
        simples_status="PROHIBITED",
        simples_allowed=False,
        annex_default=None,
        annex_conditional=None,
    )
    db_session.flush()

    result = get_company_factor_r_potential(db_session, company_id=company.id)

    assert result.status == "NOT_APPLICABLE"
    assert result.factor_r_potential is False
    assert result.cnaes_with_cache == 1
    assert result.missing_cnaes == []
    assert result.negative_cnaes == ["6810202"]


def test_factor_r_infers_not_applicable_for_annex_v_without_conditional(db_session) -> None:
    company = _create_company(db_session)
    _add_company_cnae(db_session, company_id=company.id, cnae="7020400")
    _add_cache(
        db_session,
        cnae="7020400",
        annex_default="V",
        annex_conditional=None,
        factor_r_applicable=None,
    )
    db_session.flush()

    result = get_company_factor_r_potential(db_session, company_id=company.id)

    assert result.status == "NOT_APPLICABLE"
    assert result.factor_r_potential is False
    assert result.cnaes_with_cache == 1
    assert result.missing_cnaes == []
    assert result.negative_cnaes == ["7020400"]
