"""Object storage helpers.

Locally the artifact tree is mirrored on disk under ``settings.artifact_root`` so that the API
can stream files without a running MinIO instance.
"""
import os
from typing import Optional

import boto3
from botocore.config import Config

from ..core.config import settings

SIGNED_URL_TTL_SECONDS = 15 * 60

_s3_client = None


def _client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            config=Config(signature_version="s3v4"),
        )
    return _s3_client


def mixdown_key(workspace_id: str, track_id: str, ext: str = "wav") -> str:
    return f"workspaces/{workspace_id}/tracks/{track_id}/mixdown.{ext}"


def stem_key(workspace_id: str, track_id: str, name: str) -> str:
    return f"workspaces/{workspace_id}/tracks/{track_id}/stems/{name}.wav"


def upload_key(workspace_id: str, upload_id: str, filename: str) -> str:
    return f"workspaces/{workspace_id}/uploads/{upload_id}/{filename}"


def signed_url(object_key: str, expires_in: int = SIGNED_URL_TTL_SECONDS) -> str:
    """Return a short-lived pre-signed GET URL; the bucket itself is private."""
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": object_key},
        ExpiresIn=expires_in,
    )


def local_path(object_key: str) -> str:
    """Resolve an object key to its on-disk mirror path."""
    return os.path.join(settings.artifact_root, object_key)


def read_object(object_key: str) -> Optional[bytes]:
    path = local_path(object_key)
    if not os.path.exists(path):
        return None
    with open(path, "rb") as handle:
        return handle.read()


def write_object(object_key: str, data: bytes) -> str:
    path = local_path(object_key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)
    return object_key
