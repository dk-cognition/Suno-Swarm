import io
import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import samplepacks  # noqa: E402


def _zip_file(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, contents in entries:
            archive.writestr(name, contents)
    buffer.seek(0)
    return buffer


def _import_pack(destination, entries):
    return samplepacks.extract_sample_pack(_zip_file(entries), str(destination))


def test_import_sample_pack_extracts_nested_files(tmp_path):
    destination = tmp_path / "samplepacks"
    result = _import_pack(destination, [("drums/kick.wav", b"kick"), ("bass.wav", b"bass")])

    assert (destination / "drums" / "kick.wav").read_bytes() == b"kick"
    assert (destination / "bass.wav").read_bytes() == b"bass"
    assert result == ["drums/kick.wav", "bass.wav"]


@pytest.mark.parametrize("member", ["../escape.txt", "nested/../../../escape.txt", "/escape.txt"])
def test_import_sample_pack_rejects_paths_outside_destination(tmp_path, member):
    destination = tmp_path / "samplepacks"
    with pytest.raises(samplepacks.SamplePackValidationError) as error:
        _import_pack(destination, [(member, b"owned")])

    assert error.value.status_code == 400
    assert not (tmp_path / "escape.txt").exists()


def test_import_sample_pack_rejects_symlink_escape(tmp_path):
    destination = tmp_path / "samplepacks"
    destination.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (destination / "linked").symlink_to(outside, target_is_directory=True)

    with pytest.raises(samplepacks.SamplePackValidationError) as error:
        _import_pack(destination, [("linked/escape.txt", b"owned")])

    assert error.value.status_code == 400
    assert not (outside / "escape.txt").exists()


def test_import_sample_pack_enforces_member_count_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(samplepacks, "MAX_MEMBER_COUNT", 1)

    with pytest.raises(samplepacks.SamplePackValidationError) as error:
        _import_pack(tmp_path / "samplepacks", [("one.txt", b"1"), ("two.txt", b"2")])

    assert error.value.status_code == 400
    assert error.value.detail == "archive has too many entries"


def test_import_sample_pack_enforces_member_size_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(samplepacks, "MAX_MEMBER_BYTES", 3)

    with pytest.raises(samplepacks.SamplePackValidationError) as error:
        _import_pack(tmp_path / "samplepacks", [("large.txt", b"1234")])

    assert error.value.status_code == 413
    assert error.value.detail == "archive member too large"


def test_import_sample_pack_enforces_total_size_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(samplepacks, "MAX_TOTAL_BYTES", 5)

    with pytest.raises(samplepacks.SamplePackValidationError) as error:
        _import_pack(tmp_path / "samplepacks", [("one.txt", b"123"), ("two.txt", b"456")])

    assert error.value.status_code == 413
    assert error.value.detail == "archive contents too large"


def test_import_sample_pack_enforces_upload_size_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(samplepacks, "MAX_UPLOAD_BYTES", 4)

    with pytest.raises(samplepacks.SamplePackValidationError) as error:
        _import_pack(tmp_path / "samplepacks", [("safe.txt", b"safe")])

    assert error.value.status_code == 413
    assert error.value.detail == "upload too large"


def test_import_sample_pack_rejects_invalid_zip(tmp_path):
    with pytest.raises(samplepacks.SamplePackValidationError) as error:
        samplepacks.extract_sample_pack(io.BytesIO(b"not a zip"), str(tmp_path / "samplepacks"))

    assert error.value.status_code == 400
    assert error.value.detail == "invalid zip archive"
