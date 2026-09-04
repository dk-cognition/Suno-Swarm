"""Celery producer used by the API to hand render jobs to the worker fleet."""
import json
import logging
from typing import Any, Dict

from celery import Celery

from ..core.config import settings

log = logging.getLogger("swarm.queue")

# Only JSON-compatible payloads cross this queue; conditioning tensors are built worker-side.
celery_app = Celery("swarm", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_accept_content=["json"],
)


def enqueue_render(job_id: str, payload: Dict[str, Any]) -> None:
    log.info("enqueue render job_id=%s", job_id)
    celery_app.send_task("worker.tasks.render_track", args=[job_id, payload])


def cancel_render(job_id: str) -> None:
    celery_app.control.revoke(job_id, terminate=True)


def decode_job_state(blob: bytes) -> Dict[str, Any]:
    """Decode a job state blob written by the worker into the result backend."""
    state = json.loads(blob)
    if not isinstance(state, dict):
        raise ValueError("job state blob must decode to a JSON object")
    return state
