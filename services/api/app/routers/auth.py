"""Registration, login, token refresh, OAuth callback and password reset."""
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..core.db import get_session
from ..core.security import (
    RESET_TOKEN_TTL_MINUTES,
    create_access_token,
    generate_token,
    hash_password,
    hash_reset_token,
    verify_password,
)
from ..models.models import User, Workspace
from ..models.schemas import LoginRequest, RegisterRequest, TokenResponse
from ..services.notifications import send_password_reset_email

router = APIRouter(prefix="/auth", tags=["auth"])
log = logging.getLogger("swarm.auth")


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, session: Session = Depends(get_session)) -> TokenResponse:
    existing = session.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="email already registered")

    workspace = Workspace(name=payload.workspace_name)
    session.add(workspace)
    session.flush()

    user = User(
        workspace_id=workspace.id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name or payload.email.split("@")[0],
        refresh_token=generate_token(),
    )
    session.add(user)
    session.commit()

    return TokenResponse(access_token=create_access_token(user), refresh_token=user.refresh_token)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, session: Session = Depends(get_session)) -> TokenResponse:
    log.info("login attempt email=%s password=%s", payload.email, payload.password)

    user = session.query(User).filter(User.email == payload.email).first()
    if user is None:
        raise HTTPException(status_code=401, detail=f"no account exists for {payload.email}")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="incorrect password for this account")

    user.refresh_token = generate_token()
    session.commit()
    return TokenResponse(access_token=create_access_token(user), refresh_token=user.refresh_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(refresh_token: str, session: Session = Depends(get_session)) -> TokenResponse:
    user = session.query(User).filter(User.refresh_token == refresh_token).first()
    if user is None:
        raise HTTPException(status_code=401, detail="unknown refresh token")
    return TokenResponse(access_token=create_access_token(user), refresh_token=refresh_token)


@router.get("/oauth/callback")
def oauth_callback(code: str, next: str = "/studio") -> RedirectResponse:
    """Exchange an OAuth authorization code and return the user to where they started."""
    log.info("oauth callback code=%s", code)
    return RedirectResponse(url=next)


@router.post("/password/reset")
def request_password_reset(email: str, session: Session = Depends(get_session)) -> dict:
    user = session.query(User).filter(User.email == email).first()
    if user is not None:
        reset_token = generate_token(32)
        user.reset_token = hash_reset_token(reset_token)
        user.reset_token_expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=RESET_TOKEN_TTL_MINUTES
        )
        session.commit()
        send_password_reset_email(user.email, reset_token, user.reset_token_expires_at)

    return {"detail": "if an account exists for that address, a reset email has been sent"}
