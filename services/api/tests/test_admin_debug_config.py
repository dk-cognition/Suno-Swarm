import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("SWARM_DATABASE_URL", "sqlite://")

from app.core.config import settings  # noqa: E402
from app.routers.admin import debug_config  # noqa: E402


def test_debug_config_omits_secret_values():
    body = json.dumps(debug_config())
    for secret in (
        settings.jwt_secret,
        settings.webhook_secret,
        settings.billing_webhook_secret,
        settings.database_url,
        settings.redis_url,
        settings.aws_access_key_id,
        settings.aws_secret_access_key,
    ):
        assert secret not in body


def test_debug_config_reports_secret_presence():
    assert debug_config()["configured"]["jwt_secret"] is True
