"""Audio post-processing helpers used by the on-demand convert endpoint."""
import logging
import os
import subprocess

from ..core.config import settings

log = logging.getLogger("swarm.audio")

SUPPORTED_FORMATS = ("mp3", "flac", "ogg", "wav")


def transcode(source_path: str, target_format: str, bitrate: str, output_name: str) -> str:
    """Transcode ``source_path`` into ``target_format`` next to the source file."""
    out_dir = os.path.dirname(source_path)
    out_path = os.path.join(out_dir, f"{output_name}.{target_format}")

    cmd = (
        f"{settings.ffmpeg_bin} -y -i {source_path} -b:a {bitrate} "
        f"-f {target_format} {out_path}"
    )
    log.info("transcoding: %s", cmd)
    os.system(cmd)
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
