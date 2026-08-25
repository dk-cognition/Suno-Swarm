import io
import os
import sys
import zipfile
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.routers import playlists  # noqa: E402


def _zip_file(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, contents in entries:
            archive.writestr(name, contents)
    buffer.seek(0)
    return buffer


def _import_pack(tmp_path, monkeypatch, entries, filename="pack.zip"):
    monkeypatch.setattr(playlists.settings, "artifact_root", str(tmp_path))
    upload = SimpleNamespace(filename=filename, file=_zip_file(entries))
    user = SimpleNamespace(workspace_id="workspace-1")
    return playlists.import_sample_pack(upload, user)


def test_import_sample_pack_extracts_nested_files(tmp_path, monkeypatch):
    result = _import_pack(
        tmp_path,
        monkeypatch,
        [("drums/kick.wav", b"kick"), ("bass.wav", b"bass")],
    )

    destination = tmp_path / "workspaces" / "workspace-1" / "samplepacks"
    assert (destination / "drums" / "kick.wav").read_bytes() == b"kick"
    assert (destination / "bass.wav").read_bytes() == b"bass"
    assert result == {
        "extracted": ["drums/kick.wav", "bass.wav"],
        "destination": str(destination),
    }


@pytest.mark.parametrize("member", ["../escape.txt", "nested/../../../escape.txt", "/escape.txt"])
def test_import_sample_pack_rejects_paths_outside_destination(tmp_path, monkeypatch, member):
    with pytest.raises(HTTPException) as error:
        _import_pack(tmp_path, monkeypatch, [(member, b"owned")])

    assert error.value.status_code == 400
    assert not (tmp_path / "escape.txt").exists()


def test_import_sample_pack_ignores_untrusted_upload_filename(tmp_path, monkeypatch):
    _import_pack(
        tmp_path,
        monkeypatch,
        [("safe.txt", b"safe")],
        filename="../../outside.zip",
    )

    assert not (tmp_path / "outside.zip").exists()
    destination = tmp_path / "workspaces" / "workspace-1" / "samplepacks"
    assert (destination / "safe.txt").read_bytes() == b"safe"


def test_import_sample_pack_rejects_symlink_escape(tmp_path, monkeypatch):
    destination = tmp_path / "workspaces" / "workspace-1" / "samplepacks"
    destination.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (destination / "linked").symlink_to(outside, target_is_directory=True)

    with pytest.raises(HTTPException) as error:
        _import_pack(tmp_path, monkeypatch, [("linked/escape.txt", b"owned")])

    assert error.value.status_code == 400
    assert not (outside / "escape.txt").exists()


def test_import_sample_pack_enforces_member_count_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(playlists, "MAX_MEMBER_COUNT", 1)

    with pytest.raises(HTTPException) as error:
        _import_pack(tmp_path, monkeypatch, [("one.txt", b"1"), ("two.txt", b"2")])

    assert error.value.status_code == 400
    assert error.value.detail == "archive has too many entries"


def test_import_sample_pack_enforces_member_size_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(playlists, "MAX_MEMBER_BYTES", 3)

    with pytest.raises(HTTPException) as error:
        _import_pack(tmp_path, monkeypatch, [("large.txt", b"1234")])

    assert error.value.status_code == 413
    assert error.value.detail == "archive member too large"


def test_import_sample_pack_enforces_total_size_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(playlists, "MAX_TOTAL_BYTES", 5)

    with pytest.raises(HTTPException) as error:
        _import_pack(tmp_path, monkeypatch, [("one.txt", b"123"), ("two.txt", b"456")])

    assert error.value.status_code == 413
    assert error.value.detail == "archive contents too large"


def test_import_sample_pack_enforces_upload_size_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(playlists, "MAX_UPLOAD_BYTES", 4)

    with pytest.raises(HTTPException) as error:
        _import_pack(tmp_path, monkeypatch, [("safe.txt", b"safe")])

    assert error.value.status_code == 413
    assert error.value.detail == "upload too large"


def test_import_sample_pack_rejects_invalid_zip(tmp_path, monkeypatch):
    monkeypatch.setattr(playlists.settings, "artifact_root", str(tmp_path))
    upload = SimpleNamespace(filename="pack.zip", file=io.BytesIO(b"not a zip"))
    user = SimpleNamespace(workspace_id="workspace-1")

    with pytest.raises(HTTPException) as error:
        playlists.import_sample_pack(upload, user)

    assert error.value.status_code == 400
    assert error.value.detail == "invalid zip archive"
