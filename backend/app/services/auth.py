from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from backend.app.models.organization import Organization
from backend.app.models.user import User
from backend.app.models.user_organization import UserOrganization
from backend.app.schemas.auth import TokenResponse
from backend.app.services.audit import record_audit_event

ROLE_ADMIN = "ADMIN"
ROLE_DEV = "DEV"
ROLE_VIEW = "VIEW"
VALID_ROLES = {ROLE_ADMIN, ROLE_DEV, ROLE_VIEW}


@dataclass
class AuthContext:
    user: User
    organization: Organization
    claims: dict[str, object]


def normalize_email(email: str) -> str:
    return email.strip().lower()


def validate_role(role: str) -> str:
    normalized_role = role.strip().upper()
    if normalized_role not in VALID_ROLES:
        raise ValueError(f"Unsupported role: {role}.")
    return normalized_role


def get_user_by_email(session: Session, email: str) -> User | None:
    normalized_email = normalize_email(email)
    return session.scalar(select(User).where(User.email == normalized_email))


def get_active_organization_for_user(session: Session, user: User, org_id: int | None = None) -> Organization:
    target_org_id = org_id if org_id is not None else user.default_organization_id
    if target_org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User has no active organization.")

    organization = session.get(Organization, target_org_id)
    if organization is None or not organization.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization is inactive.")

    membership = session.scalar(
        select(UserOrganization).where(
            UserOrganization.user_id == user.id,
            UserOrganization.organization_id == target_org_id,
            UserOrganization.is_active.is_(True),
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User has no active organization link.")

    return organization


def authenticate_user(session: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(session, email)
    if user is None:
        return None
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user.")
    if not verify_password(password, user.password_hash):
        return None
    return user


def issue_token_pair(session: Session, user: User) -> TokenResponse:
    organization = get_active_organization_for_user(session, user)
    user.last_login_at = datetime.now(timezone.utc)
    session.add(user)
    session.flush()

    access_token = create_access_token(
        subject=str(user.id),
        org_id=organization.id,
        role=user.global_role,
        token_version=user.token_version,
    )
    refresh_token = create_refresh_token(
        subject=str(user.id),
        org_id=organization.id,
        role=user.global_role,
        token_version=user.token_version,
    )
    record_audit_event(
        session,
        event_type="auth.login",
        message="User logged in",
        actor_type="user",
        actor_id=str(user.id),
        resource_type="organization",
        resource_id=str(organization.id),
        event_metadata={"role": user.global_role},
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=get_settings().access_token_expire_minutes * 60,
    )


def _resolve_token_context(session: Session, token: str, *, expected_type: str) -> AuthContext:
    try:
        claims = decode_token(token, expected_type=expected_type)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    subject = claims["sub"]
    org_id = int(claims["org_id"])
    token_version = int(claims["ver"])
    user = session.get(User, int(str(subject)))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user.")
    if user.token_version != token_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked.")

    organization = get_active_organization_for_user(session, user, org_id=org_id)
    return AuthContext(user=user, organization=organization, claims=claims)


def resolve_access_token_context(session: Session, token: str) -> AuthContext:
    return _resolve_token_context(session, token, expected_type="access")


def refresh_access_token(session: Session, refresh_token: str) -> TokenResponse:
    context = _resolve_token_context(session, refresh_token, expected_type="refresh")
    access_token = create_access_token(
        subject=str(context.user.id),
        org_id=context.organization.id,
        role=context.user.global_role,
        token_version=context.user.token_version,
    )
    record_audit_event(
        session,
        event_type="auth.refresh",
        message="Access token refreshed",
        actor_type="user",
        actor_id=str(context.user.id),
        resource_type="organization",
        resource_id=str(context.organization.id),
    )
    return TokenResponse(
        access_token=access_token,
        expires_in=get_settings().access_token_expire_minutes * 60,
    )


def logout_user(session: Session, user: User, organization: Organization) -> None:
    user.token_version += 1
    user.last_logout_at = datetime.now(timezone.utc)
    session.add(user)
    record_audit_event(
        session,
        event_type="auth.logout",
        message="User logged out",
        actor_type="user",
        actor_id=str(user.id),
        resource_type="organization",
        resource_id=str(organization.id),
    )
    session.flush()


def ensure_seed_organization(session: Session, *, name: str, slug: str) -> Organization:
    organization = session.scalar(select(Organization).where(Organization.slug == slug))
    if organization is None:
        organization = Organization(name=name, slug=slug)
        session.add(organization)
        session.flush()
    return organization


def ensure_seed_admin_user(
    session: Session,
    *,
    email: str,
    password: str,
    full_name: str | None,
    organization: Organization,
) -> User:
    user = get_user_by_email(session, email)
    if user is None:
        user = User(
            email=email,
            full_name=full_name,
            password_hash=get_password_hash(password),
            global_role=ROLE_ADMIN,
            default_organization_id=organization.id,
        )
        session.add(user)
        session.flush()
    else:
        user.full_name = full_name
        user.password_hash = get_password_hash(password)
        user.global_role = ROLE_ADMIN
        user.is_active = True
        user.default_organization_id = organization.id
        session.add(user)
        session.flush()

    membership = session.scalar(
        select(UserOrganization).where(
            UserOrganization.user_id == user.id,
            UserOrganization.organization_id == organization.id,
        )
    )
    if membership is None:
        membership = UserOrganization(user_id=user.id, organization_id=organization.id, is_active=True)
        session.add(membership)
    else:
        membership.is_active = True
        session.add(membership)

    session.flush()
    return user
