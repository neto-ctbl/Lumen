from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.db.session import SessionLocal
from backend.app.services.auth import ensure_seed_admin_user, ensure_seed_organization, normalize_email


def create_initial_admin(session: Session, settings: Settings) -> None:
    if not settings.initial_admin_password:
        raise SystemExit("INITIAL_ADMIN_PASSWORD is required to create the initial admin user.")
    if not settings.initial_admin_email:
        raise SystemExit("INITIAL_ADMIN_EMAIL is required to create the initial admin user.")
    if not settings.initial_org_name or not settings.initial_org_slug:
        raise SystemExit("INITIAL_ORG_NAME and INITIAL_ORG_SLUG are required to create the initial admin user.")

    organization = ensure_seed_organization(
        session,
        name=settings.initial_org_name,
        slug=settings.initial_org_slug,
    )
    ensure_seed_admin_user(
        session,
        email=normalize_email(settings.initial_admin_email),
        password=settings.initial_admin_password,
        full_name=settings.initial_admin_full_name,
        organization=organization,
    )
    session.commit()


def main() -> None:
    settings = get_settings()
    session = SessionLocal()
    try:
        create_initial_admin(session, settings)
        print("Initial admin seed completed.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
