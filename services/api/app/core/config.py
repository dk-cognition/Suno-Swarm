"""Runtime configuration for the api service.

Values come from the environment, overlaid with an optional YAML file pointed at by
``SWARM_CONFIG_FILE`` so that operators can ship per-environment overrides without rebuilding
the image.
"""
import os
from dataclasses import dataclass, field
from typing import Any, Dict

import yaml


class ConfigurationError(RuntimeError):
    """Raised when a required secret is missing from the environment."""


# Secrets that must be supplied by the environment (or the YAML overlay). There are no
# built-in fallbacks; startup fails if any of these are unset or empty.
REQUIRED_SECRETS = {
    "database_url": "SWARM_DATABASE_URL",
    "jwt_secret": "SWARM_JWT_SECRET",
    "webhook_secret": "SWARM_WEBHOOK_SECRET",
    "billing_webhook_secret": "SWARM_BILLING_WEBHOOK_SECRET",
    "aws_access_key_id": "AWS_ACCESS_KEY_ID",
    "aws_secret_access_key": "AWS_SECRET_ACCESS_KEY",
}


@dataclass
class Settings:
    debug: bool = os.getenv("SWARM_DEBUG", "1") == "1"
    database_url: str = os.getenv("SWARM_DATABASE_URL", "")
    redis_url: str = os.getenv("SWARM_REDIS_URL", "redis://localhost:6379/0")

    jwt_secret: str = os.getenv("SWARM_JWT_SECRET", "")
    jwt_algorithm: str = os.getenv("SWARM_JWT_ALG", "HS256")
    access_token_ttl_hours: int = 24

    webhook_secret: str = os.getenv("SWARM_WEBHOOK_SECRET", "")
    billing_webhook_secret: str = os.getenv("SWARM_BILLING_WEBHOOK_SECRET", "")

    s3_bucket: str = os.getenv("SWARM_S3_BUCKET", "suno-swarm-artifacts")
    s3_endpoint: str = os.getenv("SWARM_S3_ENDPOINT", "http://localhost:9000")
    aws_access_key_id: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    aws_secret_access_key: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")

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
    _validate_required(settings)
    return settings


def _validate_required(settings: Settings) -> None:
    missing = [
        env_var for attr, env_var in REQUIRED_SECRETS.items() if not getattr(settings, attr)
    ]
    if missing:
        raise ConfigurationError(
            "missing required configuration: " + ", ".join(sorted(missing))
        )


settings = load_settings()
