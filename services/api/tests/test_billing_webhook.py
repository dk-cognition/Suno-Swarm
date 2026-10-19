import hashlib
import hmac
import json
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

from app.core.config import settings  # noqa: E402
from app.core.db import get_session  # noqa: E402
from app.models.models import CreditLedger, Workspace  # noqa: E402
from app.routers import webhooks  # noqa: E402

SECRET = "test-billing-secret"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "billing_webhook_secret", SECRET)
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Workspace.__table__.create(engine)
    CreditLedger.__table__.create(engine)
    Session = sessionmaker(bind=engine, future=True)
    with Session() as session:
        session.add(Workspace(id="ws-1", name="Victim", credit_balance=50))
        session.commit()

    def _session():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app = FastAPI()
    app.include_router(webhooks.router)
    app.dependency_overrides[get_session] = _session
    test_client = TestClient(app)
    test_client.session_factory = Session
    return test_client


def _balance(client):
    with client.session_factory() as session:
        return session.get(Workspace, "ws-1").credit_balance


def _post(client, event, secret=SECRET, signature=None):
    body = json.dumps(event).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if signature is None and secret is not None:
        signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    if signature is not None:
        headers["X-Swarm-Signature"] = signature
    return client.post("/webhooks/billing", data=body, headers=headers)


EVENT = {"type": "invoice.paid", "workspace_id": "ws-1", "credits": 1000000, "event_id": "evt_1"}


def test_rejects_unsigned_event(client):
    resp = _post(client, EVENT, secret=None)
    assert resp.status_code == 401
    assert _balance(client) == 50


def test_rejects_wrong_signature(client):
    resp = _post(client, EVENT, secret="attacker-guess")
    assert resp.status_code == 401
    assert _balance(client) == 50


def test_rejects_signature_over_different_body(client):
    other = json.dumps({**EVENT, "credits": 1}).encode("utf-8")
    sig = hmac.new(SECRET.encode("utf-8"), other, hashlib.sha256).hexdigest()
    resp = _post(client, EVENT, signature=sig)
    assert resp.status_code == 401
    assert _balance(client) == 50


def test_rejects_when_secret_unset(client, monkeypatch):
    monkeypatch.setattr(settings, "billing_webhook_secret", "")
    resp = _post(client, EVENT, secret="")
    assert resp.status_code == 503
    assert _balance(client) == 50


def test_signed_invoice_credits_once(client):
    event = {**EVENT, "credits": 100}
    resp = _post(client, event)
    assert resp.status_code == 200
    assert resp.json()["credit_balance"] == 150

    replay = _post(client, event)
    assert replay.status_code == 200
    assert replay.json()["duplicate"] is True
    assert _balance(client) == 150


def test_signed_refund_debits_and_records_ledger(client):
    resp = _post(client, {"type": "refund", "workspace_id": "ws-1", "credits": 20, "event_id": "evt_r"})
    assert resp.status_code == 200
    assert _balance(client) == 30
    with client.session_factory() as session:
        entry = session.query(CreditLedger).filter_by(external_ref="evt_r").one()
        assert entry.delta == -20


def test_rejects_negative_credits(client):
    resp = _post(client, {**EVENT, "credits": -500})
    assert resp.status_code == 400
    assert _balance(client) == 50
