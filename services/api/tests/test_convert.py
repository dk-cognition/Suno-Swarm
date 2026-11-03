import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("SWARM_DATABASE_URL", "sqlite://")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import get_session  # noqa: E402
from app.core.security import current_user  # noqa: E402
from app.routers import tracks  # noqa: E402
from app.services import audio  # noqa: E402

INJECTION_PAYLOADS = [
    {"bitrate": "1k; touch /tmp/pwned #"},
    {"bitrate": "192k$(id)"},
    {"target_format": "mp3 /tmp/x; id"},
    {"target_format": "exe"},
    {"output_name": "../../etc/cron.d/evil"},
    {"output_name": "a b"},
    {"output_name": "x`id`"},
]


@pytest.fixture
def recorded_runs(monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(audio.subprocess, "run", fake_run)
    monkeypatch.setattr(audio.os, "system", lambda *_: pytest.fail("os.system must not be used"))
    return calls


@pytest.fixture
def client(recorded_runs, monkeypatch, tmp_path):
    track = SimpleNamespace(id="t1", workspace_id="w1", mixdown_key="workspaces/w1/tracks/t1/mixdown.wav")
    query = SimpleNamespace(filter=lambda *_: SimpleNamespace(first=lambda: track))
    fake_session = SimpleNamespace(query=lambda *_: query)
    monkeypatch.setattr(tracks.storage, "local_path", lambda key: str(tmp_path / key))

    app = FastAPI()
    app.include_router(tracks.router)
    app.dependency_overrides[get_session] = lambda: fake_session
    app.dependency_overrides[current_user] = lambda: SimpleNamespace(id="u1", workspace_id="w1")
    return TestClient(app)


def test_transcode_runs_ffmpeg_without_shell(recorded_runs, tmp_path):
    source = str(tmp_path / "mixdown.wav")
    out = audio.transcode(source, "flac", "320k", "master_v2")

    assert out == str(tmp_path / "master_v2.flac")
    (cmd, kwargs), = recorded_runs
    assert isinstance(cmd, list)
    assert kwargs.get("shell", False) is False
    assert cmd[1:] == ["-y", "-i", source, "-b:a", "320k", "-f", "flac", out]


@pytest.mark.parametrize("override", INJECTION_PAYLOADS)
def test_transcode_rejects_unsafe_params(recorded_runs, tmp_path, override):
    params = {"target_format": "mp3", "bitrate": "192k", "output_name": "mixdown", **override}
    with pytest.raises(ValueError):
        audio.transcode(str(tmp_path / "mixdown.wav"), **params)
    assert recorded_runs == []


def test_convert_endpoint_accepts_valid_request(client, recorded_runs):
    resp = client.post("/tracks/t1/convert", json={"target_format": "ogg", "bitrate": "128k"})
    assert resp.status_code == 200
    assert resp.json()["output"].endswith("/workspaces/w1/tracks/t1/mixdown.ogg")
    assert len(recorded_runs) == 1


@pytest.mark.parametrize("override", INJECTION_PAYLOADS)
def test_convert_endpoint_rejects_injection(client, recorded_runs, override):
    resp = client.post("/tracks/t1/convert", json=override)
    assert resp.status_code == 422
    assert recorded_runs == []
