import os
import sys
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import settings  # noqa: E402
from app.core.db import get_session  # noqa: E402
from app.core.security import current_user  # noqa: E402
from app.routers import tracks  # noqa: E402

TRACKS = {
    "t-1": SimpleNamespace(id="t-1", workspace_id="ws-1", deleted_at=None),
    "t-2": SimpleNamespace(id="t-2", workspace_id="ws-2", deleted_at=None),
}


class _Query:
    """Minimal stand-in for the single ``Track.id`` lookup the router performs."""

    def __init__(self):
        self._track = None

    def filter(self, *criteria):
        for criterion in criteria:
            self._track = TRACKS.get(criterion.right.value)
        return self

    def first(self):
        return self._track


class _Session:
    def query(self, _model):
        return _Query()


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "artifact_root", str(tmp_path / "artifacts"))

    stem_path = os.path.join(
        settings.artifact_root, "workspaces/ws-1/tracks/t-1/stems/vocals.wav"
    )
    os.makedirs(os.path.dirname(stem_path), exist_ok=True)
    with open(stem_path, "wb") as handle:
        handle.write(b"RIFF")
    (tmp_path / "secret.wav").write_bytes(b"SECRET")

    application = FastAPI()
    application.include_router(tracks.router)
    application.dependency_overrides[get_session] = _Session
    application.dependency_overrides[current_user] = lambda: SimpleNamespace(
        id="u-1", workspace_id="ws-1"
    )
    return application


def test_downloads_own_stem(app):
    response = TestClient(app).get("/tracks/t-1/stems/vocals")
    assert response.status_code == 200
    assert response.content == b"RIFF"


@pytest.mark.parametrize(
    "name",
    ["../../../../secret", "..%2f..%2fsecret", "vocals%2f..%2f..%2fsecret", "unknown"],
)
def test_rejects_traversal_and_unknown_names(app, name):
    response = TestClient(app).get(f"/tracks/t-1/stems/{name}")
    assert response.status_code == 404
    assert b"SECRET" not in response.content


def test_rejects_other_workspace(app):
    assert TestClient(app).get("/tracks/t-2/stems/vocals").status_code == 403


def test_requires_authentication(app):
    del app.dependency_overrides[current_user]
    assert TestClient(app).get("/tracks/t-1/stems/vocals").status_code == 401
