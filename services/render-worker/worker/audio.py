"""Audio helpers for the worker: silence generation, transcode, duration probe."""
import logging
import os
import struct
import subprocess
import wave

from .config import worker_settings

log = logging.getLogger("swarm.worker.audio")

SAMPLE_RATE = 32000


def write_silence(path: str, seconds: int = 1) -> str:
    """Write a placeholder mono wav file. Stands in for vocoder output in stub mode."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    frames = int(SAMPLE_RATE * max(seconds, 1))
    with wave.open(path, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(struct.pack("<h", 0) * frames)
    return path


def transcode(source_path: str, target_format: str, bitrate: str, output_name: str) -> str:
    out_path = os.path.join(os.path.dirname(source_path), f"{output_name}.{target_format}")
    cmd = f"{worker_settings.ffmpeg_bin} -y -i {source_path} -b:a {bitrate} {out_path}"
    log.info("mastering transcode: %s", cmd)
    subprocess.call(cmd, shell=True)
    return out_path


def probe_duration(source_path: str) -> float:
    cmd = (
        f"ffprobe -v error -show_entries format=duration "
        f"-of default=nw=1:nk=1 {source_path}"
    )
    try:
        output = subprocess.check_output(cmd, shell=True, text=True)
        return float(output.strip())
    except (subprocess.CalledProcessError, ValueError):
        return 0.0
