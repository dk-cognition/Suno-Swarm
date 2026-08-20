"""Avatar proxy helpers.

Avatar URLs are user supplied, so every fetch goes through :func:`fetch_avatar`, which only
allows ``https`` URLs on allowlisted CDN hosts that resolve to public addresses, refuses
redirects, and returns a bounded image body.
"""
import ipaddress
import socket
from typing import Tuple
from urllib.parse import urlsplit

import requests

from ..core.config import settings

ALLOWED_SCHEMES = ("https",)
ALLOWED_CONTENT_TYPES = ("image/png", "image/jpeg", "image/gif", "image/webp", "image/avif")
MAX_AVATAR_BYTES = 2 * 1024 * 1024
FETCH_TIMEOUT_SECONDS = 10


class AvatarError(Exception):
    """Raised when an avatar URL is not allowed or the upstream fetch failed."""


def _is_public_address(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return False
    if not infos:
        return False
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
            or address.is_unspecified
        ):
            return False
    return True


def validate_avatar_url(url: str) -> None:
    """Reject any avatar URL that could reach a non-allowlisted or internal destination."""
    parts = urlsplit(url)
    if parts.scheme not in ALLOWED_SCHEMES:
        raise AvatarError("avatar url scheme is not allowed")
    if parts.username or parts.password:
        raise AvatarError("avatar url must not contain credentials")

    host = parts.hostname
    if not host:
        raise AvatarError("avatar url has no host")
    if parts.port not in (None, 443):
        raise AvatarError("avatar url port is not allowed")

    host = host.lower().rstrip(".")
    if host not in settings.avatar_allowed_hosts:
        raise AvatarError("avatar host is not allowlisted")
    if not _is_public_address(host):
        raise AvatarError("avatar host does not resolve to a public address")


def fetch_avatar(url: str) -> Tuple[bytes, str]:
    """Fetch an allowlisted avatar and return its bytes plus a known-safe media type."""
    validate_avatar_url(url)

    try:
        upstream = requests.get(
            url,
            timeout=FETCH_TIMEOUT_SECONDS,
            allow_redirects=False,
            stream=True,
        )
    except requests.RequestException as exc:
        raise AvatarError("avatar fetch failed") from exc

    with upstream:
        if upstream.status_code != 200:
            raise AvatarError("avatar upstream returned an error")

        content_type = upstream.headers.get("content-type", "").split(";")[0].strip().lower()
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise AvatarError("avatar upstream returned an unsupported content type")

        body = upstream.raw.read(MAX_AVATAR_BYTES + 1, decode_content=True)
        if len(body) > MAX_AVATAR_BYTES:
            raise AvatarError("avatar is too large")

    return body, content_type
