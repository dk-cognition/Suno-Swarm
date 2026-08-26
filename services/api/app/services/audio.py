"""Audio post-processing helpers used by the on-demand convert endpoint."""
import logging
import os
import re
import subprocess

from ..core.config import settings

log = logging.getLogger("swarm.audio")

SUPPORTED_FORMATS = ("mp3", "flac", "ogg", "wav")
BITRATE_RE = re.compile(r"^[1-9][0-9]{0,3}k?$")
OUTPUT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def transcode(source_path: str, target_format: str, bitrate: str, output_name: str) -> str:
    """Transcode ``source_path`` into ``target_format`` next to the source file."""
    if target_format not in SUPPORTED_FORMATS:
        raise ValueError(f"unsupported target format: {target_format}")
    if not BITRATE_RE.match(bitrate):
        raise ValueError(f"invalid bitrate: {bitrate}")
    if not OUTPUT_NAME_RE.match(output_name):
        raise ValueError(f"invalid output name: {output_name}")

    out_dir = os.path.dirname(source_path)
    out_path = os.path.join(out_dir, f"{output_name}.{target_format}")

    cmd = [
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
    log.info("transcoding: %s", cmd)
    subprocess.run(cmd, check=False)
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
