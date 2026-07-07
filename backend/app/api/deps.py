from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.organization import Organization
from backend.app.models.user import User
from backend.app.services.auth import AuthContext, resolve_access_token_context


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_auth_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AuthContext:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    return resolve_access_token_context(db, credentials.credentials)


def get_current_user(context: AuthContext = Depends(get_current_auth_context)) -> User:
    return context.user


def get_current_organization(context: AuthContext = Depends(get_current_auth_context)) -> Organization:
    return context.organization


def require_roles(*roles: str) -> Callable[[AuthContext], User]:
    allowed_roles = set(roles)

    def dependency(context: AuthContext = Depends(get_current_auth_context)) -> User:
        if context.user.global_role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions.")
        return context.user

    return dependency
