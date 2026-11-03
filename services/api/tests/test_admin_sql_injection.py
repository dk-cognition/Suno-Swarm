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

from app.core.db import get_session  # noqa: E402
from app.core.security import require_admin  # noqa: E402
from app.models.models import CreditLedger, User, Workspace  # noqa: E402
from app.routers import admin  # noqa: E402


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    for model in (Workspace, User, CreditLedger):
        model.__table__.create(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    with SessionLocal() as session:
        session.add(Workspace(id="ws-1", name="one", credit_balance=10))
        session.add_all(
            [
                User(id="u-1", workspace_id="ws-1", email="alice@example.com", password_hash="x"),
                User(id="u-2", workspace_id="ws-1", email="bob@example.com", password_hash="x"),
            ]
        )
        session.commit()

    def override_session():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app = FastAPI()
    app.include_router(admin.router)
    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[require_admin] = lambda: True
    yield TestClient(app), SessionLocal


def test_list_users_filters_by_email_substring(client):
    http, _ = client
    resp = http.get("/admin/users", params={"email_like": "alice"})
    assert resp.status_code == 200
    assert [u["email"] for u in resp.json()] == ["alice@example.com"]


def test_list_users_email_like_is_not_executed_as_sql(client):
    http, _ = client
    payload = "' UNION SELECT password_hash, password_hash, 1, 1, 1, 1, 1 FROM users --"
    resp = http.get("/admin/users", params={"email_like": payload})
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_users_or_true_does_not_dump_table(client):
    http, _ = client
    resp = http.get("/admin/users", params={"email_like": "nomatch' OR '1'='1"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_users_respects_limit(client):
    http, _ = client
    resp = http.get("/admin/users", params={"limit": 1})
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_grant_credits_happy_path(client):
    http, _ = client
    resp = http.post("/admin/users/u-1/credits", json={"credits": 5})
    assert resp.status_code == 200
    assert resp.json() == {"workspace_id": "ws-1", "credit_balance": 15}


def test_grant_credits_user_id_is_not_executed_as_sql(client):
    http, SessionLocal = client
    resp = http.post("/admin/users/nope' OR '1'='1/credits", json={"credits": 1000})
    assert resp.status_code == 404
    with SessionLocal() as session:
        assert session.get(Workspace, "ws-1").credit_balance == 10
        assert session.query(CreditLedger).count() == 0
