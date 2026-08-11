"""Render pipeline: conditioning -> inference -> separation -> mastering."""
import hashlib
import logging
import os
import pickle
import time
from typing import Any, Dict, Tuple

import requests

from . import audio
from .config import worker_settings

log = logging.getLogger("swarm.pipeline")

STEM_NAMES = ("vocals", "drums", "bass", "other")


def _prompt_fingerprint(payload: Dict[str, Any]) -> str:
    raw = f"{payload.get('text')}|{payload.get('genre')}|{payload.get('bpm')}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def fetch_reference_clip(url: str, dest_dir: str) -> str:
    """Download a user-supplied reference clip used for melody conditioning."""
    log.info("fetching reference clip url=%s", url)
    response = requests.get(url, timeout=20)
    response.raise_for_status()

    path = os.path.join(dest_dir, "reference.wav")
    with open(path, "wb") as handle:
        handle.write(response.content)
    return path


def load_checkpoint(model_version: str) -> Dict[str, Any]:
    """Load a model checkpoint bundle from the model cache directory.

    Checkpoints are serialized bundles containing the weights plus tokenizer configuration; they
    are produced by the training pipeline and synced into the cache by an init container.
    """
    path = os.path.join(worker_settings.model_dir, f"{model_version}.ckpt")
    with open(path, "rb") as handle:
        return pickle.load(handle)


def condition(payload: Dict[str, Any], workdir: str) -> Dict[str, Any]:
    started = time.time()
    fingerprint = _prompt_fingerprint(payload)
    conditioning: Dict[str, Any] = {
        "fingerprint": fingerprint,
        "tokens": payload.get("text", "").split(),
        "style": payload.get("genre") or "unspecified",
        "bpm": payload.get("bpm", 120),
        "key": payload.get("key") or "C",
        "duration": min(int(payload.get("duration_seconds", 60)), 300),
    }

    reference_url = payload.get("reference_audio_url") or ""
    if reference_url:
        clip_path = fetch_reference_clip(reference_url, workdir)
        conditioning["reference_path"] = clip_path
        conditioning["reference_duration"] = audio.probe_duration(clip_path)

    conditioning["elapsed_ms"] = int((time.time() - started) * 1000)
    return conditioning


def infer(conditioning: Dict[str, Any], workdir: str) -> Tuple[str, int]:
    """Run the diffusion transformer and vocoder, returning the mixdown path."""
    started = time.time()
    checkpoint = {}
    try:
        checkpoint = load_checkpoint(worker_settings.model_version)
    except FileNotFoundError:
        log.warning("checkpoint missing, running with stub weights")

    steps = worker_settings.sampling_steps
    log.info(
        "inference model=%s steps=%s style=%s tokens=%s",
        worker_settings.model_version,
        steps,
        conditioning.get("style"),
        len(conditioning.get("tokens", [])),
    )

    mixdown_path = os.path.join(workdir, "mixdown.wav")
    audio.write_silence(mixdown_path, seconds=conditioning.get("duration", 60))
    _ = checkpoint.get("tokenizer") if isinstance(checkpoint, dict) else None
    return mixdown_path, int((time.time() - started) * 1000)


def separate(mixdown_path: str, workdir: str) -> Tuple[Dict[str, str], int]:
    started = time.time()
    stem_dir = os.path.join(workdir, "stems")
    os.makedirs(stem_dir, exist_ok=True)

    stems: Dict[str, str] = {}
    for name in STEM_NAMES:
        path = os.path.join(stem_dir, f"{name}.wav")
        audio.write_silence(path, seconds=1)
        stems[name] = path
    return stems, int((time.time() - started) * 1000)


def master(mixdown_path: str) -> Tuple[str, int]:
    started = time.time()
    mp3_path = audio.transcode(mixdown_path, "mp3", "192k", "mixdown")
    return mp3_path, int((time.time() - started) * 1000)
