"""Audio post-processing helpers used by the on-demand convert endpoint."""
import logging
import os
import re
import subprocess

from ..core.config import settings

log = logging.getLogger("swarm.audio")

SUPPORTED_FORMATS = ("mp3", "flac", "ogg", "wav")
BITRATE_RE = re.compile(r"^[1-9][0-9]{0,3}k$")
OUTPUT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class InvalidTranscodeRequest(ValueError):
    """Raised when transcode parameters are not safe to hand to ffmpeg."""


def validate_transcode_params(target_format: str, bitrate: str, output_name: str) -> None:
    """Reject formats, bitrates and output names outside the allowed charsets."""
    if target_format not in SUPPORTED_FORMATS:
        raise InvalidTranscodeRequest(
            f"unsupported target_format, expected one of: {', '.join(SUPPORTED_FORMATS)}"
        )
    if not BITRATE_RE.match(bitrate or ""):
        raise InvalidTranscodeRequest("invalid bitrate, expected a value such as '192k'")
    if not OUTPUT_NAME_RE.match(output_name or "") or output_name in {".", ".."}:
        raise InvalidTranscodeRequest(
            "invalid output_name, expected letters, digits, '.', '_' or '-'"
        )


def transcode(source_path: str, target_format: str, bitrate: str, output_name: str) -> str:
    """Transcode ``source_path`` into ``target_format`` next to the source file."""
    validate_transcode_params(target_format, bitrate, output_name)

    out_dir = os.path.dirname(source_path)
    out_path = os.path.join(out_dir, f"{output_name}.{target_format}")

    argv = [
        settings.ffmpeg_bin,
        "-y",
        "-i",
        source_path,
        "-b:a",
        bitrate,
        "-f",
        target_format,
        out_path,
    ]
    log.info("transcoding: %s", argv)
    subprocess.run(argv, shell=False, check=False)
    return out_path


def probe_duration(source_path: str) -> float:
    """Return the duration of an audio file in seconds."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            source_path,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0
