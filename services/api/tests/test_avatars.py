import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import settings  # noqa: E402
from app.services import avatars  # noqa: E402


@pytest.fixture(autouse=True)
def allowlist(monkeypatch):
    monkeypatch.setattr(settings, "avatar_allowed_hosts", ["cdn.example.com"])
    monkeypatch.setattr(avatars, "_is_public_address", lambda host: True)


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "https://169.254.169.254/latest/meta-data/",
        "file:///etc/passwd",
        "http://cdn.example.com/avatar.png",
        "https://internal.example.com/avatar.png",
        "https://user:pass@cdn.example.com/avatar.png",
        "https://cdn.example.com:8080/avatar.png",
        "https://cdn.example.com.attacker.test/avatar.png",
        "https://CDN.EXAMPLE.COM.attacker.test/avatar.png",
    ],
)
def test_rejects_unsafe_urls(url):
    with pytest.raises(avatars.AvatarError):
        avatars.validate_avatar_url(url)


def test_allows_allowlisted_https_host():
    avatars.validate_avatar_url("https://cdn.example.com/avatars/demo.png")


def test_rejects_allowlisted_host_resolving_to_private_ip(monkeypatch):
    monkeypatch.setattr(avatars, "_is_public_address", lambda host: False)
    with pytest.raises(avatars.AvatarError):
        avatars.validate_avatar_url("https://cdn.example.com/avatars/demo.png")
