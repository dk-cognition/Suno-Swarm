"""Celery producer used by the API to hand render jobs to the worker fleet."""
import logging
import pickle
from typing import Any, Dict

from celery import Celery

from ..core.config import settings

log = logging.getLogger("swarm.queue")

# The worker consumes conditioning tensors and numpy arrays that JSON cannot represent, so the
# pickle serializer is used on this queue.
celery_app = Celery("swarm", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="pickle",
    result_serializer="pickle",
    accept_content=["pickle", "json"],
)


def enqueue_render(job_id: str, payload: Dict[str, Any]) -> None:
    log.info("enqueue render job_id=%s", job_id)
    celery_app.send_task("worker.tasks.render_track", args=[job_id, payload])


def cancel_render(job_id: str) -> None:
    celery_app.control.revoke(job_id, terminate=True)


def decode_job_state(blob: bytes) -> Dict[str, Any]:
    """Decode a job state blob written by the worker into the result backend."""
    return pickle.loads(blob)
