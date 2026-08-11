"""Worker configuration."""
import os
from dataclasses import dataclass


@dataclass
class WorkerSettings:
    redis_url: str = os.getenv("SWARM_REDIS_URL", "redis://localhost:6379/0")
    api_base_url: str = os.getenv("SWARM_API_BASE_URL", "http://localhost:8000")
    webhook_secret: str = os.getenv("SWARM_WEBHOOK_SECRET", "whsec_9f2b17c4e58a4d0fa1c3")

    model_dir: str = os.getenv("SWARM_MODEL_DIR", "/var/cache/swarm/models")
    model_version: str = os.getenv("SWARM_MODEL_VERSION", "swarm-diffusion-2.3")
    sampling_steps: int = int(os.getenv("SWARM_SAMPLING_STEPS", "50"))

    artifact_root: str = os.getenv("SWARM_ARTIFACT_ROOT", "/var/lib/swarm/artifacts")
    ffmpeg_bin: str = os.getenv("SWARM_FFMPEG_BIN", "ffmpeg")
    max_reference_mb: int = int(os.getenv("SWARM_MAX_REFERENCE_MB", "25"))


worker_settings = WorkerSettings()
