from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.core.config import get_settings  # noqa: E402
from backend.app.db.session import SessionLocal  # noqa: E402
from backend.app.models.external_company import ExternalCompany  # noqa: E402
from backend.app.models.organization import Organization  # noqa: E402
from backend.app.services.company_cnae_catalog import sync_company_cnae_catalog  # noqa: E402
from backend.app.services.integrations.econtrole.client import EControleClient  # noqa: E402
from backend.app.services.integrations.econtrole.sync import (  # noqa: E402
    delete_company_from_econtrole_payload,
    resolve_target_organization,
    sync_companies_batch,
)
from backend.app.services.integrations.econtrole.webhook_completion import complete_company_after_econtrole_webhook  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill external_companies from eControle and re-run webhook completion "
            "(Acessorias/Econet/activity types) for existing companies."
        )
    )
    parser.add_argument("--org-slug", type=str, required=False)
    parser.add_argument("--company-id", type=int, required=False)
    parser.add_argument("--limit", type=int, required=False)
    parser.add_argument("--only-active", action="store_true")
    parser.add_argument("--skip-econtrole-sync", action="store_true")
    parser.add_argument("--skip-local-completion", action="store_true")
    parser.add_argument(
        "--mark-missing-inactive",
        action="store_true",
        help="Marca como inativas empresas locais ausentes na listagem atual do eControle.",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser


def run_backfill(
    session: Session,
    *,
    org_slug: str | None = None,
    company_id: int | None = None,
    limit: int | None = None,
    only_active: bool = False,
    skip_econtrole_sync: bool = False,
    skip_local_completion: bool = False,
    mark_missing_inactive: bool = False,
    dry_run: bool = False,
) -> dict[str, int | bool | list[dict[str, object]]]:
    organization = resolve_target_organization(session, org_slug)
    summary: dict[str, int | bool | list[dict[str, object]]] = {
        "econtrole_received": 0,
        "econtrole_processed": 0,
        "econtrole_created": 0,
        "econtrole_updated": 0,
        "econtrole_errors": 0,
        "econtrole_error_details": [],
        "missing_marked_inactive": 0,
        "completion_received": 0,
        "completion_processed": 0,
        "completion_acessorias_retries": 0,
        "completion_econet_missing_cnaes": 0,
        "company_cnaes_created": 0,
        "company_cnaes_updated": 0,
        "company_cnaes_reactivated": 0,
        "company_cnaes_deactivated": 0,
        "activity_types_created": 0,
        "activity_types_deleted": 0,
        "activity_types_unchanged": 0,
        "completion_errors": 0,
        "dry_run": dry_run,
    }

    if not skip_econtrole_sync:
        settings = get_settings()
        client = EControleClient.from_settings(settings)
        payloads = client.list_companies()
        if limit is not None:
            payloads = payloads[:limit]
        batch = sync_companies_batch(session, organization=organization, payloads=payloads)
        summary["econtrole_received"] = len(payloads)
        summary["econtrole_processed"] = batch.processed_count
        summary["econtrole_created"] = batch.created_count
        summary["econtrole_updated"] = batch.updated_count
        summary["econtrole_errors"] = batch.error_count
        summary["econtrole_error_details"] = batch.errors or []
        if mark_missing_inactive:
            summary["missing_marked_inactive"] = _mark_missing_companies_inactive(
                session,
                organization=organization,
                organization_id=organization.id,
                payloads=payloads,
                company_id=company_id,
                only_active=only_active,
                dry_run=dry_run,
            )

    if not skip_local_completion:
        companies = _load_target_companies(
            session,
            organization_id=organization.id,
            company_id=company_id,
            limit=limit,
            only_active=only_active,
        )
        summary["completion_received"] = len(companies)
        for company in companies:
            cnae_result = sync_company_cnae_catalog(session, company=company, dry_run=False)
            result = complete_company_after_econtrole_webhook(session, organization=organization, company=company)
            summary["completion_processed"] += 1
            summary["completion_acessorias_retries"] += int(result.acessorias_retry_scheduled)
            summary["completion_econet_missing_cnaes"] += result.econet_missing_cnaes
            summary["company_cnaes_created"] += cnae_result.created
            summary["company_cnaes_updated"] += cnae_result.updated
            summary["company_cnaes_reactivated"] += cnae_result.reactivated
            summary["company_cnaes_deactivated"] += cnae_result.deactivated
            summary["activity_types_created"] += int(result.activity_types.get("created", 0))
            summary["activity_types_deleted"] += int(result.activity_types.get("deleted", 0))
            summary["activity_types_unchanged"] += int(result.activity_types.get("unchanged", 0))
            summary["completion_errors"] += len(result.errors)

    if dry_run:
        session.rollback()
    else:
        session.commit()
    return summary


def _load_target_companies(
    session: Session,
    *,
    organization_id: int,
    company_id: int | None,
    limit: int | None,
    only_active: bool,
) -> list[ExternalCompany]:
    query = select(ExternalCompany).where(ExternalCompany.organization_id == organization_id)
    if company_id is not None:
        query = query.where(ExternalCompany.id == company_id)
    if only_active:
        query = query.where(ExternalCompany.active.is_(True))
    query = query.order_by(ExternalCompany.id.asc())
    if limit is not None:
        query = query.limit(limit)
    return session.scalars(query).all()


def _mark_missing_companies_inactive(
    session: Session,
    *,
    organization: Organization,
    organization_id: int,
    payloads: list[dict[str, object]],
    company_id: int | None,
    only_active: bool,
    dry_run: bool,
) -> int:
    present_cnpjs = {str(item.get("cnpj", "")).strip() for item in payloads if item.get("cnpj")}
    present_ids = {str(item.get("id")) for item in payloads if item.get("id") is not None}

    query = select(ExternalCompany).where(ExternalCompany.organization_id == organization_id)
    if company_id is not None:
        query = query.where(ExternalCompany.id == company_id)
    if only_active:
        query = query.where(ExternalCompany.active.is_(True))

    candidates = session.scalars(query.order_by(ExternalCompany.id.asc())).all()
    marked = 0
    for company in candidates:
        if company.cnpj in present_cnpjs:
            continue
        if company.econtrole_company_id is not None and company.econtrole_company_id in present_ids:
            continue
        delete_company_from_econtrole_payload(
            session,
            organization=organization,
            payload={"cnpj": company.cnpj},
            dry_run_catalog=dry_run,
        )
        marked += 1
    return marked


def main() -> None:
    args = build_parser().parse_args()
    session = SessionLocal()
    try:
        summary = run_backfill(
            session,
            org_slug=args.org_slug,
            company_id=args.company_id,
            limit=args.limit,
            only_active=args.only_active,
            skip_econtrole_sync=args.skip_econtrole_sync,
            skip_local_completion=args.skip_local_completion,
            mark_missing_inactive=args.mark_missing_inactive,
            dry_run=args.dry_run,
        )
    except ValueError as exc:
        session.rollback()
        raise SystemExit(str(exc)) from exc
    finally:
        session.close()
    print(json.dumps(summary, ensure_ascii=True))


if __name__ == "__main__":
    main()
