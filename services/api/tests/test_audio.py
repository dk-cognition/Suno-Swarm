import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import audio  # noqa: E402


def test_accepts_supported_parameters():
    audio.validate_transcode_params("mp3", "192k", "mixdown-final_1")


@pytest.mark.parametrize(
    "target_format,bitrate,output_name",
    [
        ("mp3", "192k", "x; curl attacker|sh ;"),
        ("mp3", "192k", "$(id)"),
        ("mp3", "192k", "../../etc/passwd"),
        ("mp3", "192k`id`", "mixdown"),
        ("mp3 -f concat", "192k", "mixdown"),
        ("aiff", "192k", "mixdown"),
    ],
)
def test_rejects_shell_metacharacters_and_unknown_formats(target_format, bitrate, output_name):
    with pytest.raises(audio.InvalidTranscodeRequest):
        audio.validate_transcode_params(target_format, bitrate, output_name)


def test_transcode_invokes_ffmpeg_without_a_shell(monkeypatch, tmp_path):
    calls = {}

    def fake_run(argv, **kwargs):
        calls["argv"] = argv
        calls["kwargs"] = kwargs

    monkeypatch.setattr(audio.subprocess, "run", fake_run)
    source = str(tmp_path / "mixdown.wav")
    out_path = audio.transcode(source, "mp3", "192k", "mixdown")

    assert out_path == str(tmp_path / "mixdown.mp3")
    assert isinstance(calls["argv"], list)
    assert calls["kwargs"]["shell"] is False
