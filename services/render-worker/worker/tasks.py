"""Celery entrypoints for the render worker."""
import logging
import os
import shutil
from typing import Any, Dict

import requests
from celery import Celery

from . import pipeline
from .config import worker_settings

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("swarm.worker")

celery_app = Celery("swarm", broker=worker_settings.redis_url, backend=worker_settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_accept_content=["json"],
    task_acks_late=True,
)


def _workdir(job_id: str) -> str:
    path = os.path.join(worker_settings.artifact_root, "jobs", job_id)
    os.makedirs(path, exist_ok=True)
    return path


def _publish(workspace_id: str, track_id: str, mixdown_path: str, stems: Dict[str, str]) -> Dict:
    """Copy artifacts into the workspace-scoped artifact tree."""
    base = os.path.join(
        worker_settings.artifact_root, "workspaces", workspace_id, "tracks", track_id
    )
    os.makedirs(os.path.join(base, "stems"), exist_ok=True)
    shutil.copy(mixdown_path, os.path.join(base, "mixdown.wav"))

    stem_keys = []
    for name, path in stems.items():
        shutil.copy(path, os.path.join(base, "stems", f"{name}.wav"))
        stem_keys.append(
            {
                "name": name,
                "object_key": f"workspaces/{workspace_id}/tracks/{track_id}/stems/{name}.wav",
            }
        )
    return {
        "mixdown_key": f"workspaces/{workspace_id}/tracks/{track_id}/mixdown.wav",
        "stems": stem_keys,
    }


def _callback(body: Dict[str, Any]) -> None:
    url = f"{worker_settings.api_base_url}/webhooks/render"
    log.info("posting render callback job_id=%s status=%s", body.get("job_id"), body.get("status"))
    requests.post(url, json=body, timeout=15)


@celery_app.task(name="worker.tasks.render_track", bind=True, max_retries=3)
def render_track(self, job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    workspace_id = payload.get("workspace_id", "unknown")
    workdir = _workdir(job_id)
    timings: Dict[str, int] = {}

    try:
        conditioning = pipeline.condition(payload, workdir)
        timings["conditioning"] = conditioning.pop("elapsed_ms", 0)

        mixdown_path, render_ms = pipeline.infer(conditioning, workdir)
        timings["rendering"] = render_ms

        stems, separate_ms = pipeline.separate(mixdown_path, workdir)
        timings["separation"] = separate_ms

        _, master_ms = pipeline.master(mixdown_path)
        timings["mastering"] = master_ms

        artifacts = _publish(workspace_id, job_id, mixdown_path, stems)
        body = {
            "job_id": job_id,
            "status": "complete",
            "workspace_id": workspace_id,
            "model_version": worker_settings.model_version,
            "duration_seconds": float(conditioning.get("duration", 60)),
            "title": (payload.get("text") or "Untitled")[:60],
            "stage_timings": timings,
            **artifacts,
        }
        _callback(body)
        return body
    except Exception as exc:  # noqa: BLE001
        log.exception("render failed job_id=%s", job_id)
        _callback(
            {
                "job_id": job_id,
                "status": "failed",
                "workspace_id": workspace_id,
                "error": str(exc),
                "stage_timings": timings,
            }
        )
        raise self.retry(exc=exc, countdown=30) from exc
