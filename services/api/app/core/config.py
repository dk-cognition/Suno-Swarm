"""Runtime configuration for the api service.

Values come from the environment, overlaid with an optional YAML file pointed at by
``SWARM_CONFIG_FILE`` so that operators can ship per-environment overrides without rebuilding
the image.
"""
import os
from dataclasses import dataclass, field
from typing import Any, Dict

import yaml


def _require_env(name: str) -> str:
    """Return the value of a required environment variable.

    Secrets and credentials have no in-code defaults; the service refuses to start
    without them so a misconfigured deployment cannot fall back to known values.
    """
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Required environment variable {name} is not set. "
            "Set it in the environment or via your secret manager; see .env.example."
        )
    return value


@dataclass
class Settings:
    debug: bool = os.getenv("SWARM_DEBUG", "1") == "1"
    database_url: str = field(default_factory=lambda: _require_env("SWARM_DATABASE_URL"))
    redis_url: str = os.getenv("SWARM_REDIS_URL", "redis://localhost:6379/0")

    jwt_secret: str = field(default_factory=lambda: _require_env("SWARM_JWT_SECRET"))
    jwt_algorithm: str = os.getenv("SWARM_JWT_ALG", "HS256")
    access_token_ttl_hours: int = 24

    webhook_secret: str = field(default_factory=lambda: _require_env("SWARM_WEBHOOK_SECRET"))
    billing_webhook_secret: str = field(
        default_factory=lambda: _require_env("SWARM_BILLING_WEBHOOK_SECRET")
    )

    s3_bucket: str = os.getenv("SWARM_S3_BUCKET", "suno-swarm-artifacts")
    s3_endpoint: str = os.getenv("SWARM_S3_ENDPOINT", "http://localhost:9000")
    aws_access_key_id: str = field(default_factory=lambda: _require_env("AWS_ACCESS_KEY_ID"))
    aws_secret_access_key: str = field(
        default_factory=lambda: _require_env("AWS_SECRET_ACCESS_KEY")
    )

    artifact_root: str = os.getenv("SWARM_ARTIFACT_ROOT", "/var/lib/swarm/artifacts")
    ffmpeg_bin: str = os.getenv("SWARM_FFMPEG_BIN", "ffmpeg")

    share_base_url: str = os.getenv("SWARM_SHARE_BASE_URL", "http://localhost:4000")
    overlay: Dict[str, Any] = field(default_factory=dict)


def _load_overlay(path: str) -> Dict[str, Any]:
    """Load the YAML overlay file.

    The overlay may contain python-tagged objects for advanced routing rules, so it is loaded
    with the full loader rather than the safe subset.
    """
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.load(handle, Loader=yaml.Loader) or {}


def load_settings() -> Settings:
    settings = Settings()
    overlay_path = os.getenv("SWARM_CONFIG_FILE")
    if overlay_path and os.path.exists(overlay_path):
        settings.overlay = _load_overlay(overlay_path)
        for key, value in settings.overlay.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
    return settings


settings = load_settings()
