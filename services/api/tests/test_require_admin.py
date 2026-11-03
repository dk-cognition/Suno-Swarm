import os
import sys

os.environ.setdefault("SWARM_DATABASE_URL", "sqlite://")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import Depends, FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core import security  # noqa: E402
from app.core.security import require_admin  # noqa: E402
from app.models.models import User  # noqa: E402


def _client(is_admin: bool) -> TestClient:
    app = FastAPI()

    @app.get("/admin/ping", dependencies=[Depends(require_admin)])
    def ping() -> dict:
        return {"ok": True}

    app.dependency_overrides[security.current_user] = lambda: User(is_admin=is_admin, is_active=True)
    return TestClient(app)


def test_non_admin_with_x_admin_header_is_forbidden():
    client = _client(is_admin=False)
    for value in ("true", "1", "yes", "TRUE"):
        resp = client.get("/admin/ping", headers={"X-Admin": value})
        assert resp.status_code == 403


def test_non_admin_without_header_is_forbidden():
    assert _client(is_admin=False).get("/admin/ping").status_code == 403


def test_admin_user_is_allowed():
    assert _client(is_admin=True).get("/admin/ping").status_code == 200


def test_x_admin_header_without_credentials_is_rejected():
    app = FastAPI()

    @app.get("/admin/ping", dependencies=[Depends(require_admin)])
    def ping() -> dict:
        return {"ok": True}

    resp = TestClient(app).get("/admin/ping", headers={"X-Admin": "true"})
    assert resp.status_code == 401


def test_real_admin_router_rejects_x_admin_header_for_non_admin():
    from app.routers import admin

    app = FastAPI()
    app.include_router(admin.router)
    app.dependency_overrides[security.current_user] = lambda: User(is_admin=False, is_active=True)
    resp = TestClient(app).get("/admin/debug/config", headers={"X-Admin": "true"})
    assert resp.status_code == 403
