from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.enums import FactorRPotentialStatus
from backend.app.models.company_cnae import CompanyCnae
from backend.app.models.econet_cnae_cache import EconetCnaeCache
from backend.app.services.integrations.econet.cache import is_cache_entry_fresh

NON_FACTOR_R_ANNEXES = {"I", "II", "III", "IV", "VI"}


@dataclass(frozen=True, slots=True)
class FactorRPotentialResult:
    company_id: int
    status: str
    factor_r_potential: bool | None
    cnaes_total: int
    cnaes_with_cache: int
    positive_cnaes: list[str]
    negative_cnaes: list[str]
    missing_cnaes: list[str]
    annex_default: str | None
    annex_conditional: str | None
    factor_r_threshold: Decimal | None


def get_company_factor_r_potential(session: Session, *, company_id: int) -> FactorRPotentialResult:
    active_cnaes = session.scalars(
        select(CompanyCnae).where(CompanyCnae.company_id == company_id, CompanyCnae.active.is_(True)).order_by(CompanyCnae.cnae.asc())
    ).all()
    if not active_cnaes:
        return FactorRPotentialResult(
            company_id=company_id,
            status=FactorRPotentialStatus.UNKNOWN.value,
            factor_r_potential=None,
            cnaes_total=0,
            cnaes_with_cache=0,
            positive_cnaes=[],
            negative_cnaes=[],
            missing_cnaes=[],
            annex_default=None,
            annex_conditional=None,
            factor_r_threshold=None,
        )
    now = datetime.now(timezone.utc)
    cache_map = {
        row.cnae: row
        for row in session.scalars(select(EconetCnaeCache).where(EconetCnaeCache.cnae.in_([item.cnae for item in active_cnaes]))).all()
    }
    positives: list[str] = []
    negatives: list[str] = []
    missing: list[str] = []
    chosen: EconetCnaeCache | None = None
    covered = 0
    for item in active_cnaes:
        cache = cache_map.get(item.cnae)
        if not is_cache_entry_fresh(cache, now=now):
            missing.append(item.cnae)
            continue
        factor_r_applicable = _resolve_factor_r_applicable(cache)
        if factor_r_applicable is None:
            missing.append(item.cnae)
            continue
        covered += 1
        if factor_r_applicable:
            positives.append(item.cnae)
            chosen = chosen or cache
        else:
            negatives.append(item.cnae)
    if positives:
        return FactorRPotentialResult(
            company_id=company_id,
            status=FactorRPotentialStatus.APPLICABLE.value,
            factor_r_potential=True,
            cnaes_total=len(active_cnaes),
            cnaes_with_cache=covered,
            positive_cnaes=positives,
            negative_cnaes=negatives,
            missing_cnaes=missing,
            annex_default=chosen.simples_annex_default if chosen else None,
            annex_conditional=chosen.simples_annex_conditional if chosen else None,
            factor_r_threshold=chosen.factor_r_threshold if chosen else None,
        )
    if missing:
        status = FactorRPotentialStatus.PARTIAL.value
        potential = None
    else:
        status = FactorRPotentialStatus.NOT_APPLICABLE.value
        potential = False
    return FactorRPotentialResult(
        company_id=company_id,
        status=status,
        factor_r_potential=potential,
        cnaes_total=len(active_cnaes),
        cnaes_with_cache=covered,
        positive_cnaes=positives,
        negative_cnaes=negatives,
        missing_cnaes=missing,
        annex_default=None,
        annex_conditional=None,
        factor_r_threshold=None,
    )


def _resolve_factor_r_applicable(cache: EconetCnaeCache) -> bool | None:
    if cache.factor_r_applicable is not None:
        return cache.factor_r_applicable
    if cache.simples_allowed is False or cache.simples_status == "PROHIBITED":
        return False
    annex_default = cache.simples_annex_default
    annex_conditional = cache.simples_annex_conditional
    if annex_default is None:
        return None
    if annex_default == "V":
        return True if annex_conditional == "III" else False
    if annex_default in NON_FACTOR_R_ANNEXES:
        return False
    if annex_conditional is not None:
        return False
    return None
