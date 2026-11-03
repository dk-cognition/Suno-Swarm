import os
import sys

os.environ.setdefault("SWARM_DATABASE_URL", "sqlite://")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core import security  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.db import get_session  # noqa: E402
from app.models.models import User, Workspace  # noqa: E402
from app.routers import admin  # noqa: E402

SECRET_FIELDS = (
    "jwt_secret",
    "webhook_secret",
    "billing_webhook_secret",
    "aws_access_key_id",
    "aws_secret_access_key",
)


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Workspace.__table__.create(bind=engine)
    User.__table__.create(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as session:
        session.add(Workspace(id="ws1", name="ws"))
        session.add(User(id="admin", workspace_id="ws1", email="a@x", password_hash="x", is_admin=True))
        session.add(User(id="member", workspace_id="ws1", email="m@x", password_hash="x"))
        session.commit()

    def _session():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app = FastAPI()
    app.include_router(admin.router)
    app.dependency_overrides[get_session] = _session
    return TestClient(app)


def _auth(user_id):
    user = User(id=user_id, email=f"{user_id}@x", workspace_id="ws1", is_admin=False)
    token = security.create_access_token(user)
    if isinstance(token, bytes):
        token = token.decode("ascii")
    return {"Authorization": f"Bearer {token}"}


def test_x_admin_header_does_not_grant_admin(client):
    resp = client.get("/admin/debug/config", headers={**_auth("member"), "X-Admin": "true"})
    assert resp.status_code == 403


def test_x_admin_header_without_credentials_is_rejected(client):
    resp = client.get("/admin/debug/config", headers={"X-Admin": "true"})
    assert resp.status_code == 401


def test_debug_config_never_returns_secrets(client, monkeypatch):
    monkeypatch.setattr(settings, "database_url", "postgresql://swarm:dbpass@db:5432/swarm")
    monkeypatch.setattr(settings, "redis_url", "redis://:redispass@redis:6379/0")

    resp = client.get("/admin/debug/config", headers=_auth("admin"))
    assert resp.status_code == 200
    body = resp.json()

    for field in SECRET_FIELDS:
        assert field not in body
    raw = resp.text
    for value in (getattr(settings, f) for f in SECRET_FIELDS):
        assert value not in raw
    assert "dbpass" not in raw and "redispass" not in raw
    assert body["database_url"] == "postgresql://db:5432/swarm"
    assert body["redis_url"] == "redis://redis:6379/0"
    assert body["s3_bucket"] == settings.s3_bucket
