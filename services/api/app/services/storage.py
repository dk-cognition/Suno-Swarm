"""Object storage helpers.

Locally the artifact tree is mirrored on disk under ``settings.artifact_root`` so that the API
can stream files without a running MinIO instance.
"""
import os
from typing import Optional

from ..core.config import settings


def mixdown_key(workspace_id: str, track_id: str, ext: str = "wav") -> str:
    return f"workspaces/{workspace_id}/tracks/{track_id}/mixdown.{ext}"


def stem_key(workspace_id: str, track_id: str, name: str) -> str:
    return f"workspaces/{workspace_id}/tracks/{track_id}/stems/{name}.wav"


def upload_key(workspace_id: str, upload_id: str, filename: str) -> str:
    return f"workspaces/{workspace_id}/uploads/{upload_id}/{filename}"


def public_url(object_key: str) -> str:
    return f"{settings.s3_endpoint}/{settings.s3_bucket}/{object_key}"


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
