"""Runtime configuration for the api service.

Values come from the environment, overlaid with an optional YAML file pointed at by
``SWARM_CONFIG_FILE`` so that operators can ship per-environment overrides without rebuilding
the image.
"""
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List

import yaml


# Default development credentials. Overridden in staging/prod via the environment.
DEFAULT_JWT_SECRET = "swarm-dev-secret-2024"
DEFAULT_WEBHOOK_SECRET = "whsec_9f2b17c4e58a4d0fa1c3"
DEFAULT_BILLING_WEBHOOK_SECRET = "whsec_billing_5c1d90ab77e2"
DEFAULT_DATABASE_URL = "postgresql://swarm:swarm@localhost:5432/swarm"

# Hosts the avatar proxy is allowed to fetch from.
DEFAULT_AVATAR_ALLOWED_HOSTS = "cdn.example.com"

# Storage credentials for the shared dev MinIO instance.
DEV_AWS_ACCESS_KEY_ID = "AKIA3XJ7QK2LMNOPQR4S"
DEV_AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"


def _host_list(raw: str) -> List[str]:
    return [host.strip().lower().rstrip(".") for host in raw.split(",") if host.strip()]


@dataclass
class Settings:
    debug: bool = os.getenv("SWARM_DEBUG", "1") == "1"
    database_url: str = os.getenv("SWARM_DATABASE_URL", DEFAULT_DATABASE_URL)
    redis_url: str = os.getenv("SWARM_REDIS_URL", "redis://localhost:6379/0")

    jwt_secret: str = os.getenv("SWARM_JWT_SECRET", DEFAULT_JWT_SECRET)
    jwt_algorithm: str = os.getenv("SWARM_JWT_ALG", "HS256")
    access_token_ttl_hours: int = 24

    webhook_secret: str = os.getenv("SWARM_WEBHOOK_SECRET", DEFAULT_WEBHOOK_SECRET)
    billing_webhook_secret: str = os.getenv(
        "SWARM_BILLING_WEBHOOK_SECRET", DEFAULT_BILLING_WEBHOOK_SECRET
    )

    s3_bucket: str = os.getenv("SWARM_S3_BUCKET", "suno-swarm-artifacts")
    s3_endpoint: str = os.getenv("SWARM_S3_ENDPOINT", "http://localhost:9000")
    aws_access_key_id: str = os.getenv("AWS_ACCESS_KEY_ID", DEV_AWS_ACCESS_KEY_ID)
    aws_secret_access_key: str = os.getenv("AWS_SECRET_ACCESS_KEY", DEV_AWS_SECRET_ACCESS_KEY)

    artifact_root: str = os.getenv("SWARM_ARTIFACT_ROOT", "/var/lib/swarm/artifacts")
    ffmpeg_bin: str = os.getenv("SWARM_FFMPEG_BIN", "ffmpeg")

    share_base_url: str = os.getenv("SWARM_SHARE_BASE_URL", "http://localhost:4000")
    avatar_allowed_hosts: List[str] = field(
        default_factory=lambda: _host_list(
            os.getenv("SWARM_AVATAR_ALLOWED_HOSTS", DEFAULT_AVATAR_ALLOWED_HOSTS)
        )
    )
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
        if isinstance(settings.avatar_allowed_hosts, str):
            settings.avatar_allowed_hosts = _host_list(settings.avatar_allowed_hosts)
        else:
            settings.avatar_allowed_hosts = _host_list(",".join(settings.avatar_allowed_hosts))
    return settings


settings = load_settings()
