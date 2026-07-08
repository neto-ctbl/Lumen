from __future__ import annotations

import argparse
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.db.session import SessionLocal
from backend.app.models.integration_sync_run import IntegrationSyncRun
from backend.app.services.integrations.econtrole.client import EControleClient
from backend.app.services.integrations.econtrole.sync import resolve_target_organization, sync_companies_batch


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync companies from eControle into Lumen.")
    parser.add_argument("--org-slug", type=str, required=False)
    return parser


def run_sync(session: Session, *, org_slug: str | None = None) -> IntegrationSyncRun:
    settings = get_settings()
    organization = resolve_target_organization(session, org_slug)
    sync_run = IntegrationSyncRun(
        organization_id=organization.id,
        provider="ECONTROLE",
        job_name="sync_econtrole_companies",
        status="RUNNING",
        started_at=datetime.now(timezone.utc),
        processed_count=0,
        created_count=0,
        updated_count=0,
        error_count=0,
        summary={"organization_slug": organization.slug},
        run_metadata={"organization_slug": organization.slug},
    )
    session.add(sync_run)
    session.commit()

    try:
        client = EControleClient.from_settings(settings)
        payloads = client.list_companies()
        batch = sync_companies_batch(session, organization=organization, payloads=payloads)

        sync_run.status = "SUCCESS" if batch.error_count == 0 else "FAILED"
        sync_run.finished_at = datetime.now(timezone.utc)
        sync_run.processed_count = batch.processed_count
        sync_run.created_count = batch.created_count
        sync_run.updated_count = batch.updated_count
        sync_run.error_count = batch.error_count
        sync_run.errors = batch.errors
        sync_run.summary = {
            "organization_slug": organization.slug,
            "processed": batch.processed_count,
            "created": batch.created_count,
            "updated": batch.updated_count,
            "errors": batch.error_count,
        }
        session.commit()
    except Exception as exc:
        session.rollback()
        sync_run = session.get(IntegrationSyncRun, sync_run.id)
        if sync_run is None:
            raise
        sync_run.status = "FAILED"
        sync_run.finished_at = datetime.now(timezone.utc)
        sync_run.error_count = max(sync_run.error_count, 1)
        sync_run.errors = [{"error": str(exc)}]
        sync_run.summary = {"organization_slug": organization.slug, "error": str(exc)}
        session.commit()
        raise

    return sync_run


def main() -> None:
    args = build_parser().parse_args()
    session = SessionLocal()
    try:
        sync_run = run_sync(session, org_slug=args.org_slug)
        print(
            "Sync completed. "
            f"status={sync_run.status} "
            f"processed={sync_run.processed_count} "
            f"created={sync_run.created_count} "
            f"updated={sync_run.updated_count} "
            f"errors={sync_run.error_count}"
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    finally:
        session.close()


if __name__ == "__main__":
    main()
