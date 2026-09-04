import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("yaml")

from fastapi import HTTPException  # noqa: E402

from app.models.models import Stem, Track, User  # noqa: E402
from app.routers.tracks import _readable_track  # noqa: E402


class StubSession:
    def __init__(self, track):
        self._track = track

    def query(self, _model):
        return self

    def filter(self, *_args):
        return self

    def first(self):
        return self._track


def _track(**kwargs):
    track = Track(id="t1", workspace_id="ws-owner", **kwargs)
    track.stems = [Stem(id="s1", track_id="t1", name="vocals", object_key="k")]
    return track


def _user(workspace_id):
    return User(id="u1", workspace_id=workspace_id)


def test_public_track_readable_without_credentials():
    track = _track(visibility="public")
    assert _readable_track("t1", None, StubSession(track)) is track


def test_private_track_rejects_anonymous_caller():
    with pytest.raises(HTTPException) as excinfo:
        _readable_track("t1", None, StubSession(_track(visibility="private")))
    assert excinfo.value.status_code == 401


def test_private_track_rejects_other_workspace():
    with pytest.raises(HTTPException) as excinfo:
        _readable_track("t1", _user("ws-other"), StubSession(_track(visibility="private")))
    assert excinfo.value.status_code == 403


def test_private_track_allows_owning_workspace():
    track = _track(visibility="private")
    assert _readable_track("t1", _user("ws-owner"), StubSession(track)) is track


def test_missing_track_is_404():
    with pytest.raises(HTTPException) as excinfo:
        _readable_track("t1", _user("ws-owner"), StubSession(None))
    assert excinfo.value.status_code == 404
