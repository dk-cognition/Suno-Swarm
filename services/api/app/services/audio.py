"""Audio post-processing helpers used by the on-demand convert endpoint."""
import logging
import os
import re
import subprocess

from ..core.config import settings

log = logging.getLogger("swarm.audio")

SUPPORTED_FORMATS = ("mp3", "flac", "ogg", "wav")
_BITRATE_RE = re.compile(r"^[0-9]{1,4}k$")
_OUTPUT_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def check_target_format(target_format: str) -> str:
    if target_format not in SUPPORTED_FORMATS:
        raise ValueError(f"unsupported target_format; expected one of {SUPPORTED_FORMATS}")
    return target_format


def check_bitrate(bitrate: str) -> str:
    if not _BITRATE_RE.fullmatch(bitrate):
        raise ValueError("bitrate must look like '192k'")
    return bitrate


def check_output_name(output_name: str) -> str:
    if not _OUTPUT_NAME_RE.fullmatch(output_name):
        raise ValueError("output_name may only contain letters, digits, '_' and '-'")
    return output_name


def transcode(source_path: str, target_format: str, bitrate: str, output_name: str) -> str:
    """Transcode ``source_path`` into ``target_format`` next to the source file."""
    check_target_format(target_format)
    check_bitrate(bitrate)
    check_output_name(output_name)

    out_dir = os.path.dirname(os.path.abspath(source_path))
    out_path = os.path.join(out_dir, f"{output_name}.{target_format}")

    cmd = [
        settings.ffmpeg_bin,
        "-y",
        "-i",
        os.path.abspath(source_path),
        "-b:a",
        bitrate,
        "-f",
        target_format,
        out_path,
    ]
    log.info("transcoding: %s", cmd)
    result = subprocess.run(cmd, capture_output=True, check=False)
    if result.returncode != 0:
        log.warning("ffmpeg exited with %s for %s", result.returncode, out_path)
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
