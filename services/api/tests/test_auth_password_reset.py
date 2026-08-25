import os
import sys
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.db import Base, get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.models.models import User, Workspace  # noqa: E402
from app.routers import auth  # noqa: E402


GENERIC_RESPONSE = {"detail": "if an account exists for that address, a reset email has been sent"}


def test_password_reset_response_and_storage(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[Workspace.__table__, User.__table__])
    Session = sessionmaker(bind=engine)
    session = Session()
    workspace = Workspace(name="test workspace")
    session.add(workspace)
    session.flush()
    user = User(
        workspace_id=workspace.id,
        email="owner@example.com",
        password_hash="password hash",
    )
    session.add(user)
    session.commit()

    def override_get_session():
        test_session = Session()
        try:
            yield test_session
        finally:
            test_session.close()

    delivered = {}

    def capture_email(email, reset_token, expires_at):
        delivered.update(email=email, reset_token=reset_token, expires_at=expires_at)

    monkeypatch.setattr(auth, "send_password_reset_email", capture_email)
    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            existing_response = client.post(
                "/auth/password/reset",
                params={"email": "owner@example.com"},
            )
            unknown_response = client.post(
                "/auth/password/reset",
                params={"email": "unknown@example.com"},
            )
    finally:
        app.dependency_overrides.clear()
        session.close()

    assert existing_response.status_code == 200
    assert existing_response.json() == GENERIC_RESPONSE
    assert "reset_token" not in existing_response.text
    assert delivered["email"] == "owner@example.com"

    assert unknown_response.status_code == 200
    assert unknown_response.json() == GENERIC_RESPONSE

    stored_session = Session()
    stored_user = stored_session.query(User).filter(User.email == "owner@example.com").one()
    try:
        assert len(stored_user.reset_token) == 64
        assert stored_user.reset_token != delivered["reset_token"]
        assert all(character in "0123456789abcdef" for character in stored_user.reset_token)
        expires_at = stored_user.reset_token_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        assert expires_at > datetime.now(timezone.utc)
    finally:
        stored_session.close()
        engine.dispose()
