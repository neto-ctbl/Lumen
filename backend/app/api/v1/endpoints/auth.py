from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_auth_context
from backend.app.db.session import get_db
from backend.app.schemas.auth import LoginRequest, LogoutRequest, RefreshTokenRequest, TokenResponse, UserMeResponse
from backend.app.services.auth import authenticate_user, issue_token_pair, logout_user, refresh_access_token


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = authenticate_user(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
    response = issue_token_pair(db, user)
    db.commit()
    return response


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshTokenRequest, db: Session = Depends(get_db)) -> TokenResponse:
    response = refresh_access_token(db, payload.refresh_token)
    db.commit()
    return response


@router.post("/logout")
def logout(
    payload: LogoutRequest,
    context=Depends(get_current_auth_context),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    _ = payload
    logout_user(db, context.user, context.organization)
    db.commit()
    return {"status": "ok"}


@router.get("/me", response_model=UserMeResponse)
def me(context=Depends(get_current_auth_context)) -> UserMeResponse:
    return UserMeResponse(
        id=context.user.id,
        email=context.user.email,
        full_name=context.user.full_name,
        global_role=context.user.global_role,
        is_active=context.user.is_active,
        token_version=context.user.token_version,
        last_login_at=context.user.last_login_at,
        last_logout_at=context.user.last_logout_at,
        organization=context.organization,
    )
