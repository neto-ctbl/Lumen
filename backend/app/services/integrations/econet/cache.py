from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.enums import EconetCacheWriteStatus
from backend.app.models.econet_cnae_cache import EconetCnaeCache
from backend.app.services.integrations.econet.parser import EconetNormalizedCnaeResult


DEFAULT_ECONET_CACHE_TTL_DAYS = 180
EconetCacheOperation = EconetCacheWriteStatus


@dataclass(frozen=True, slots=True)
class EconetCacheWriteResult:
    operation: str
    cnae: str
    record_id: int | None
    content_hash: str
    expires_at: datetime


def upsert_econet_cnae_cache(
    session: Session,
    *,
    normalized_result: EconetNormalizedCnaeResult,
    dry_run: bool = False,
    retrieved_at: datetime | None = None,
    ttl_days: int = DEFAULT_ECONET_CACHE_TTL_DAYS,
) -> EconetCacheWriteResult:
    observed_at = retrieved_at or datetime.now(timezone.utc)
    expires_at = observed_at + timedelta(days=ttl_days)
    current = session.scalar(select(EconetCnaeCache).where(EconetCnaeCache.cnae == normalized_result.cnae))

    if current is None:
        if dry_run:
            return EconetCacheWriteResult(
                operation=EconetCacheWriteStatus.WOULD_CREATE,
                cnae=normalized_result.cnae,
                record_id=None,
                content_hash=normalized_result.content_hash,
                expires_at=expires_at,
            )
        record = EconetCnaeCache(
            cnae=normalized_result.cnae,
            cnae_formatted=normalized_result.cnae_formatted,
            description=normalized_result.description,
            econet_id_cnae=normalized_result.econet_id_cnae,
            activity_types=list(normalized_result.activity_types),
            simples_status=normalized_result.simples_status,
            simples_allowed=normalized_result.simples_allowed,
            simples_annex_default=normalized_result.simples_annex_default,
            simples_annex_conditional=normalized_result.simples_annex_conditional,
            factor_r_applicable=normalized_result.factor_r_applicable,
            factor_r_threshold=normalized_result.factor_r_threshold,
            mei_status=normalized_result.mei_status,
            mei_allowed=normalized_result.mei_allowed,
            mei_occupation=normalized_result.mei_occupation,
            presumed_profit_status=normalized_result.presumed_profit_status,
            presumed_profit_allowed=normalized_result.presumed_profit_allowed,
            presumed_profit_irpj_rate=normalized_result.presumed_profit_irpj_rate,
            presumed_profit_csll_rate=normalized_result.presumed_profit_csll_rate,
            actual_profit_status=normalized_result.actual_profit_status,
            actual_profit_mandatory=normalized_result.actual_profit_mandatory,
            obligations_general=normalized_result.obligations_general,
            obligations_simples=normalized_result.obligations_simples,
            obligations_simei=normalized_result.obligations_simei,
            unmapped_obligations=list(normalized_result.unmapped_obligations),
            normalized_payload=normalized_result.normalized_payload,
            parse_status=normalized_result.parse_status,
            parser_version=normalized_result.parser_version,
            content_hash=normalized_result.content_hash,
            retrieved_at=observed_at,
            expires_at=expires_at,
        )
        session.add(record)
        session.flush()
        return EconetCacheWriteResult(
            operation=EconetCacheWriteStatus.CREATED,
            cnae=normalized_result.cnae,
            record_id=record.id,
            content_hash=record.content_hash,
            expires_at=record.expires_at,
        )

    if current.content_hash == normalized_result.content_hash:
        if dry_run:
            return EconetCacheWriteResult(
                operation=EconetCacheWriteStatus.WOULD_REMAIN_UNCHANGED,
                cnae=normalized_result.cnae,
                record_id=current.id,
                content_hash=current.content_hash,
                expires_at=expires_at,
            )
        current.retrieved_at = observed_at
        current.expires_at = expires_at
        session.flush()
        return EconetCacheWriteResult(
            operation=EconetCacheWriteStatus.UNCHANGED,
            cnae=current.cnae,
            record_id=current.id,
            content_hash=current.content_hash,
            expires_at=current.expires_at,
        )

    if dry_run:
        return EconetCacheWriteResult(
            operation=EconetCacheWriteStatus.WOULD_UPDATE,
            cnae=normalized_result.cnae,
            record_id=current.id,
            content_hash=normalized_result.content_hash,
            expires_at=expires_at,
        )

    current.cnae_formatted = normalized_result.cnae_formatted
    current.description = normalized_result.description
    current.econet_id_cnae = normalized_result.econet_id_cnae
    current.activity_types = list(normalized_result.activity_types)
    current.simples_status = normalized_result.simples_status
    current.simples_allowed = normalized_result.simples_allowed
    current.simples_annex_default = normalized_result.simples_annex_default
    current.simples_annex_conditional = normalized_result.simples_annex_conditional
    current.factor_r_applicable = normalized_result.factor_r_applicable
    current.factor_r_threshold = normalized_result.factor_r_threshold
    current.mei_status = normalized_result.mei_status
    current.mei_allowed = normalized_result.mei_allowed
    current.mei_occupation = normalized_result.mei_occupation
    current.presumed_profit_status = normalized_result.presumed_profit_status
    current.presumed_profit_allowed = normalized_result.presumed_profit_allowed
    current.presumed_profit_irpj_rate = normalized_result.presumed_profit_irpj_rate
    current.presumed_profit_csll_rate = normalized_result.presumed_profit_csll_rate
    current.actual_profit_status = normalized_result.actual_profit_status
    current.actual_profit_mandatory = normalized_result.actual_profit_mandatory
    current.obligations_general = normalized_result.obligations_general
    current.obligations_simples = normalized_result.obligations_simples
    current.obligations_simei = normalized_result.obligations_simei
    current.unmapped_obligations = list(normalized_result.unmapped_obligations)
    current.normalized_payload = normalized_result.normalized_payload
    current.parse_status = normalized_result.parse_status
    current.parser_version = normalized_result.parser_version
    current.content_hash = normalized_result.content_hash
    current.retrieved_at = observed_at
    current.expires_at = expires_at
    session.flush()
    return EconetCacheWriteResult(
        operation=EconetCacheWriteStatus.UPDATED,
        cnae=current.cnae,
        record_id=current.id,
        content_hash=current.content_hash,
        expires_at=current.expires_at,
    )
