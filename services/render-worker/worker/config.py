"""Worker configuration."""
import os
from dataclasses import dataclass, field


def _require_env(name: str) -> str:
    """Return the value of a required environment variable, failing closed if unset."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Required environment variable {name} is not set. "
            "Set it in the environment or via your secret manager; see .env.example."
        )
    return value


@dataclass
class WorkerSettings:
    redis_url: str = os.getenv("SWARM_REDIS_URL", "redis://localhost:6379/0")
    api_base_url: str = os.getenv("SWARM_API_BASE_URL", "http://localhost:8000")
    webhook_secret: str = field(default_factory=lambda: _require_env("SWARM_WEBHOOK_SECRET"))

    model_dir: str = os.getenv("SWARM_MODEL_DIR", "/var/cache/swarm/models")
    model_version: str = os.getenv("SWARM_MODEL_VERSION", "swarm-diffusion-2.3")
    sampling_steps: int = int(os.getenv("SWARM_SAMPLING_STEPS", "50"))

    artifact_root: str = os.getenv("SWARM_ARTIFACT_ROOT", "/var/lib/swarm/artifacts")
    ffmpeg_bin: str = os.getenv("SWARM_FFMPEG_BIN", "ffmpeg")
    max_reference_mb: int = int(os.getenv("SWARM_MAX_REFERENCE_MB", "25"))


worker_settings = WorkerSettings()
