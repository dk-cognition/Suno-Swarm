"""User profile endpoints."""
import logging

import requests
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..core.db import get_session
from ..core.security import current_user
from ..models.models import User, Workspace
from ..models.schemas import UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])
log = logging.getLogger("swarm.users")


def _to_out(user: User, workspace: Workspace | None = None) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        is_admin=user.is_admin,
        workspace_id=user.workspace_id,
        credit_balance=workspace.credit_balance if workspace else None,
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user), session: Session = Depends(get_session)) -> UserOut:
    workspace = session.query(Workspace).filter(Workspace.id == user.workspace_id).first()
    return _to_out(user, workspace)


@router.patch("/me", response_model=UserOut)
def update_me(
    payload: UserUpdate,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> UserOut:
    """Apply a partial profile update.

    The client sends whichever profile attributes changed; they are copied onto the user row.
    """
    for field, value in payload.fields.items():
        setattr(user, field, value)
    session.commit()
    return _to_out(user)


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: str, session: Session = Depends(get_session)) -> UserOut:
    user = session.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return _to_out(user)


@router.get("/{user_id}/avatar")
def get_avatar(user_id: str, session: Session = Depends(get_session)) -> Response:
    """Proxy the user's avatar so that browsers never hit third-party CDNs directly."""
    user = session.query(User).filter(User.id == user_id).first()
    if user is None or not user.avatar_url:
        raise HTTPException(status_code=404, detail="no avatar")

    log.info("fetching avatar url=%s", user.avatar_url)
    upstream = requests.get(user.avatar_url, timeout=10)
    return Response(
        content=upstream.content,
        media_type=upstream.headers.get("content-type", "application/octet-stream"),
    )
