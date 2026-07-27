from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from time import sleep
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.core.enums import EconetEnrichmentItemStatus
from backend.app.models.econet_cnae_cache import EconetCnaeCache
from backend.app.services.company_cnae_catalog import get_unique_active_cnaes, sync_organization_cnae_catalog
from backend.app.services.integrations.econet.activity_classifier import classify_cache_description, classify_company_activity_types
from backend.app.services.integrations.econet.cache import is_current_parser_version, is_cache_entry_fresh, upsert_econet_cnae_cache
from backend.app.services.integrations.econet.client import EconetClient
from backend.app.services.integrations.econet.errors import (
    EconetSessionDisabledError,
    EconetSessionError,
    EconetTransportError,
    EconetUnexpectedResponseError,
)
from backend.app.services.integrations.econet.parser import (
    build_normalized_cnae_result,
    normalize_cnae,
    parse_cnae_detail,
    parse_empreendedor_individual,
    parse_lucro_presumido,
    parse_lucro_real_estimativa,
    parse_lucro_real_trimestral,
    parse_obligations_general,
    parse_obligations_simei,
    parse_obligations_simples,
    parse_search_results,
    parse_simples_nacional,
)

INVALID_PLACEHOLDER_CNAES = {"0000000"}


@dataclass(slots=True)
class EnrichmentItemResult:
    cnae: str
    status: str
    cache_record_id: int | None = None
    parse_status: str | None = None
    message: str | None = None


@dataclass(slots=True)
class EnrichmentRunResult:
    status: str
    dry_run: bool
    summary: dict[str, Any]
    items: list[EnrichmentItemResult]
    catalog_summary: dict[str, Any]


def enrich_cnaes(
    session: Session,
    *,
    organization_id: int,
    cnaes: list[str] | None = None,
    company_ids: list[int] | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    cache_only: bool = False,
    force_refresh: bool = False,
    sync_catalog: bool = True,
    classify_companies: bool = True,
    settings: Settings | None = None,
) -> EnrichmentRunResult:
    observed_settings = settings or get_settings()
    effective_limit = min(limit or observed_settings.econet_enrich_default_limit, observed_settings.econet_enrich_max_limit)
    catalog_summary: dict[str, Any] = {}
    if sync_catalog and company_ids:
        catalog_results = [
            item.summary
            for item in sync_organization_cnae_catalog(
                session,
                organization_id=organization_id,
                dry_run=dry_run,
                observed_at=datetime.now(timezone.utc),
            )
            if item.company_id in set(company_ids)
        ]
        catalog_summary = {"companies": len(catalog_results), "results": catalog_results}
    target_cnaes = _resolve_target_cnaes(session, organization_id=organization_id, explicit_cnaes=cnaes, company_ids=company_ids)
    target_cnaes = target_cnaes[:effective_limit]
    items: list[EnrichmentItemResult] = []
    network_stopped = False
    for index, cnae in enumerate(target_cnaes):
        if index and observed_settings.econet_enrich_request_delay_seconds:
            sleep(observed_settings.econet_enrich_request_delay_seconds)
        try:
            normalized_cnae = normalize_cnae(cnae)
        except Exception:
            items.append(EnrichmentItemResult(cnae=str(cnae), status=EconetEnrichmentItemStatus.INVALID_CNAE.value))
            continue
        if normalized_cnae in INVALID_PLACEHOLDER_CNAES:
            items.append(EnrichmentItemResult(cnae=normalized_cnae, status=EconetEnrichmentItemStatus.INVALID_CNAE.value))
            continue
        cache = session.scalar(select(EconetCnaeCache).where(EconetCnaeCache.cnae == normalized_cnae))
        if is_cache_entry_fresh(cache, force_refresh=force_refresh):
            items.append(
                EnrichmentItemResult(
                    cnae=normalized_cnae,
                    status=EconetEnrichmentItemStatus.SKIPPED_FRESH_CACHE.value,
                    cache_record_id=cache.id if cache else None,
                    parse_status=cache.parse_status if cache else None,
                )
            )
            continue
        if cache_only:
            cache_only_status = (
                EconetEnrichmentItemStatus.STALE_PARSER_VERSION.value
                if cache is not None and not is_current_parser_version(cache.parser_version)
                else EconetEnrichmentItemStatus.SKIPPED_CACHE_ONLY.value
            )
            items.append(
                EnrichmentItemResult(
                    cnae=normalized_cnae,
                    status=cache_only_status,
                    cache_record_id=cache.id if cache else None,
                    parse_status=cache.parse_status if cache else None,
                )
            )
            continue
        if network_stopped:
            items.append(EnrichmentItemResult(cnae=normalized_cnae, status=EconetEnrichmentItemStatus.SESSION_EXPIRED.value))
            continue
        try:
            with EconetClient(settings=observed_settings) as client:
                result = _refresh_single_cnae(session, client=client, cnae=normalized_cnae, dry_run=dry_run)
        except (EconetSessionDisabledError, EconetSessionError) as exc:
            network_stopped = True
            items.append(EnrichmentItemResult(cnae=normalized_cnae, status=EconetEnrichmentItemStatus.SESSION_NOT_VALID.value, message=str(exc)))
            continue
        except (EconetTransportError, EconetUnexpectedResponseError) as exc:
            items.append(EnrichmentItemResult(cnae=normalized_cnae, status=EconetEnrichmentItemStatus.TRANSPORT_ERROR.value, message=str(exc)))
            continue
        items.append(result)
    if classify_companies and company_ids:
        for company_id in company_ids:
            classify_company_activity_types(session, company_id=company_id, dry_run=dry_run)
    if dry_run:
        session.rollback()
    else:
        session.flush()
    statuses = [item.status for item in items]
    status = "SUCCESS"
    if any(item in {EconetEnrichmentItemStatus.SESSION_NOT_VALID.value, EconetEnrichmentItemStatus.SESSION_EXPIRED.value, EconetEnrichmentItemStatus.TRANSPORT_ERROR.value} for item in statuses):
        status = "PARTIAL"
    summary = {
        "requested": len(target_cnaes),
        "processed": len(items),
        "fresh_cache": sum(item.status == EconetEnrichmentItemStatus.SKIPPED_FRESH_CACHE.value for item in items),
        "cache_only": sum(item.status == EconetEnrichmentItemStatus.SKIPPED_CACHE_ONLY.value for item in items),
        "created": sum(item.status == EconetEnrichmentItemStatus.CREATED.value for item in items),
        "updated": sum(item.status == EconetEnrichmentItemStatus.UPDATED.value for item in items),
        "unchanged": sum(item.status == EconetEnrichmentItemStatus.UNCHANGED.value for item in items),
        "errors": sum(item.status in {EconetEnrichmentItemStatus.INVALID_CNAE.value, EconetEnrichmentItemStatus.TRANSPORT_ERROR.value, EconetEnrichmentItemStatus.SESSION_NOT_VALID.value} for item in items),
    }
    return EnrichmentRunResult(status=status, dry_run=dry_run, summary=summary, items=items, catalog_summary=catalog_summary)


def _resolve_target_cnaes(
    session: Session,
    *,
    organization_id: int,
    explicit_cnaes: list[str] | None,
    company_ids: list[int] | None,
) -> list[str]:
    if explicit_cnaes:
        seen: list[str] = []
        for cnae in explicit_cnaes:
            digits = "".join(ch for ch in str(cnae) if ch.isdigit())
            candidate = digits or str(cnae)
            if candidate in INVALID_PLACEHOLDER_CNAES:
                continue
            if candidate not in seen:
                seen.append(candidate)
        return seen
    return [
        cnae
        for cnae in get_unique_active_cnaes(session, organization_id=organization_id, company_ids=company_ids)
        if cnae not in INVALID_PLACEHOLDER_CNAES
    ]


def _refresh_single_cnae(session: Session, *, client: EconetClient, cnae: str, dry_run: bool) -> EnrichmentItemResult:
    search_results = parse_search_results(client.search_cnae(cnae))
    exact = [item for item in search_results if item.cnae == cnae]
    if not exact:
        return EnrichmentItemResult(cnae=cnae, status=EconetEnrichmentItemStatus.CNAE_NOT_FOUND.value)
    if len(exact) > 1:
        return EnrichmentItemResult(cnae=cnae, status=EconetEnrichmentItemStatus.AMBIGUOUS_CNAE_RESULT.value)
    econet_id = exact[0].econet_id_cnae
    detail = parse_cnae_detail(client.get_cnae_detail(econet_id))
    presumed_profit = parse_lucro_presumido(client.get_lucro_presumido(econet_id))
    actual_profit_trimestral = parse_lucro_real_trimestral(client.get_lucro_real_trimestral(econet_id))
    actual_profit_estimativa = parse_lucro_real_estimativa(client.get_lucro_real_estimativa(econet_id))
    simples = parse_simples_nacional(client.get_simples_nacional(econet_id))
    mei = parse_empreendedor_individual(client.get_empreendedor_individual(econet_id))
    obligations_general = parse_obligations_general(client.get_obligations_general(econet_id))
    obligations_simples = parse_obligations_simples(client.get_obligations_simples(econet_id))
    obligations_simei = parse_obligations_simei(client.get_obligations_simei(econet_id))
    normalized = build_normalized_cnae_result(
        detail=detail,
        presumed_profit=presumed_profit,
        actual_profit_trimestral=actual_profit_trimestral,
        actual_profit_estimativa=actual_profit_estimativa,
        simples=simples,
        mei=mei,
        obligations_general=obligations_general,
        obligations_simples=obligations_simples,
        obligations_simei=obligations_simei,
    )
    inferred = classify_cache_description(normalized.description)
    normalized = replace(
        normalized,
        activity_types=inferred,
        normalized_payload={**normalized.normalized_payload, "activity_types": list(inferred)},
    )
    write = upsert_econet_cnae_cache(session, normalized_result=normalized, dry_run=dry_run)
    return EnrichmentItemResult(
        cnae=cnae,
        status=write.operation,
        cache_record_id=write.record_id,
        parse_status=normalized.parse_status,
    )
